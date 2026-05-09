import logging

import smbus2
import time
import math
import numpy as np

from src.core.filter import LowPassFilter2ndOrder
from src.core.utils import wrap_angle
from src.raspberry.hardware.sensors.mpu6050 import MPU6050

class IMUFilter:
    """
    A complementary filter type to
    apply on on IMU sensor. Basically it will be used
    on the Z-axis rotation
    """
    
    def __init__(self, alpha=0.2): # Alpha proche de 0 = filtrage fort
        self.alpha = alpha
        self.filtered_val = 0

    def filter(self, new_val):
        self.filtered_val = (self.alpha * new_val) + ((1 - self.alpha) * self.filtered_val)
        return self.filtered_val
    
class IMUFilter2Order:
    
    def __init__(self, cutoff_freq, fs):
        self.f = LowPassFilter2ndOrder(cutoff_freq=cutoff_freq, fs=fs)
    
    def filter(self, new_val):
        return self.f.update(new_val)


class IMUSensor:
    def __init__(self, name, bus_number=1, address=0x68, lpf_1_alpha=1):
        """
        Initialize the IMUSensor instance
        
        :param lpf_1_alpha: the first order low pass filter coefficient 
            applied on the gyro z-axis  angular velocity
        """
        
        self.name = name
        self.bus = smbus2.SMBus(bus_number)
        self.address = address
        
        self.accel = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.gyro  = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.orientation = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}
        
        self._mpu = IMUSensorMPu(address=address)
        
        #self._setup_sensor()
        self.last_update = time.perf_counter()
        
        self.gyro_bias = 0.0
        self.is_calibrated = False
        
        self.filter = IMUFilter2Order(fs=100, cutoff_freq=0.05)
        self.gyro_z_filter = IMUFilter(alpha=lpf_1_alpha) #IMUFilter2Order(fs=100, cutoff_freq=5) #IMUFilter(alpha=0.999) # IMUFilter2Order(fs=100, cutoff_freq=0.05)
        
    def calibrate(self, samples=200):
        self._mpu.calibrate_gyro()
        self.is_calibrated = True
        
        self.gyro_bias = self._mpu.gyro_offsets[2]

    def _setup_sensor(self):
        """
        Init configuration 
        """
        # Exemple pour MPU-6050 : Sortir du mode veille
        #self.bus.write_byte_data(self.address, 0x6B, 0)
        #print(f"IMU {self.name} initialisée à l'adresse {hex(self.address)}")

    def _read_raw_data(self, addr):
        """
        Read 2 bytes and convert them into signed value
        """
        high = self.bus.read_byte_data(self.address, addr)
        low = self.bus.read_byte_data(self.address, addr + 1)
        val = (high << 8) + low
        if val > 32768:
            val = val - 65536
        return val

    def update(self):
        """
        Read raw data and update the state
        """
        try:
            now = time.perf_counter()
            dt = now - self.last_update
            
            # Accelorometers - TODO: Read datacheet
            #self.accel['x'] = self._read_raw_data(0x3B) / 16384.0
            #self.accel['y'] = self._read_raw_data(0x3D) / 16384.0
            #self.accel['z'] = self._read_raw_data(0x3F) / 16384.0

            # Gyroscope deg per second
            #self.gyro['x'] = self._read_raw_data(0x43) / 131.0
            #self.gyro['y'] = self._read_raw_data(0x45) / 131.0
            
            
            self.gyro['x'], self.gyro['y'], gyro_z_instant  = self._mpu.get_gyro() 
            
            gyro_z_instant = gyro_z_instant
            gyro_z_instant = gyro_z_instant
            
            self.gyro['z'] = self.gyro_z_filter.filter(gyro_z_instant)

            # 3. Intégration du Yaw (Lacet)
            # Integrate only if we are not in the deadband
            if abs(gyro_z_instant) > 0.001:
                self.orientation['yaw'] += (gyro_z_instant * dt)
                self.orientation['yaw'] = wrap_angle(self.orientation['yaw'], deg=True)
            
            self.last_update = now
        except OSError as e:
            logging.warning("[IMUSensor] os error", e)

    def get_data(self):
        """
        Get the full data
        """
        return self.accel, self.gyro, self.orientation['yaw']
        
    def stop(self):
        logging.info("IMU Sensor: stopped")
        

class IMUSensorMPu:
    def __init__(self, address=0x68, cal_size=500):
        self.mpu = MPU6050(address)
        self.cal_size = cal_size

        self.gyro_offsets = np.zeros(3)
        self.theta = np.zeros(3)

        self.last_time = None

    # -----------------------------
    # Calibration
    # -----------------------------
    def calibrate_gyro(self):
        print("Calibrating gyro... keep IMU still")

        samples = []

        for _ in range(self.cal_size):
            try:
                self.mpu.get_gyro_data()
            except:
                continue

        while len(samples) < self.cal_size:
            try:
                wx, wy, wz = self.mpu.get_gyro_data()
                samples.append([wx, wy, wz])
            except:
                continue

        self.gyro_offsets = np.mean(samples, axis=0)
        print("Calibration done:", self.gyro_offsets)

    # -----------------------------
    # Raw Sensor Access
    # -----------------------------
    def get_gyro(self):
        wx, wy, wz = self.mpu.get_gyro_data()
        return np.array([wx, wy, wz]) - self.gyro_offsets

    def get_accel(self):
        ax, ay, az = self.mpu.get_accel_data()
        return np.array([ax, ay, az])

    # -----------------------------
    # Accelerometer Angles
    # -----------------------------
    def accel_to_angles(self, accel):
        ax, ay, az = accel

        # Roll (x-axis)
        roll = np.degrees(np.arctan2(ay, az))

        # Pitch (y-axis)
        pitch = np.degrees(np.arctan2(-ax, np.sqrt(ay**2 + az**2)))

        return np.array([roll, pitch])

    # -----------------------------
    # Update Step (for Kalman)
    # -----------------------------
    def update(self):
        """
        Returns:
            gyro (deg/s)
            accel_angles (deg) -> [roll, pitch]
            dt (seconds)
        """
        current_time = time.time()

        if self.last_time is None:
            self.last_time = current_time
            return None, None, 0

        dt = current_time - self.last_time
        self.last_time = current_time

        try:
            gyro = self.get_gyro()
            accel = self.get_accel()
        except:
            return None, None, dt

        accel_angles = self.accel_to_angles(accel)

        return gyro, accel_angles, dt