import logging

import smbus2
import time
import math

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


class IMUSensor:
    def __init__(self, name, bus_number=1, address=0x68):
        self.name = name
        self.bus = smbus2.SMBus(bus_number)
        self.address = address
        
        self.accel = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.gyro  = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.orientation = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}
        
        self._setup_sensor()
        self.last_update = time.perf_counter()
        
        self.gyro_bias = 0.0
        self.is_calibrated = False
        
        self.filter = IMUFilter()
        
    def calibrate(self, samples=200):
        #print("Calibration de l'IMU... Ne pas bouger !")
        sums = 0
        for _ in range(samples):
            # IL FAUT LIRE LE CAPTEUR RÉELLEMENT ICI
            raw_z = self._read_raw_data(0x47)
            sums += raw_z / 131.0  # Conversion en deg/s
            time.sleep(0.005)      # On peut réduire le sleep pour calibrer plus vite
            
        self.gyro_bias = sums / samples
        self.is_calibrated = True
        #print(f"Calibration terminée. Biais: {self.gyro_bias:.4f} deg/s")

    def _setup_sensor(self):
        """
        Init configuration 
        """
        # Exemple pour MPU-6050 : Sortir du mode veille
        self.bus.write_byte_data(self.address, 0x6B, 0)
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
            self.accel['x'] = self._read_raw_data(0x3B) / 16384.0
            self.accel['y'] = self._read_raw_data(0x3D) / 16384.0
            self.accel['z'] = self._read_raw_data(0x3F) / 16384.0

            # Gyroscope deg per second
            self.gyro['x'] = self._read_raw_data(0x43) / 131.0
            self.gyro['y'] = self._read_raw_data(0x45) / 131.0
            
            # On soustrait le biais ici pour avoir la vitesse angulaire pure
            gyro_z_instant = (self._read_raw_data(0x47) / 131.0) - self.gyro_bias
            self.gyro['z'] = gyro_z_instant

            # 3. Intégration du Yaw (Lacet)
            # On n'intègre que si le mouvement dépasse un petit seuil (Deadband)
            if abs(gyro_z_instant) > 0.05: # Filtre de bruit de 0.05 deg/s
                self.orientation['yaw'] += self.filter.filter(gyro_z_instant * dt)
            
            self.last_update = now
        except OSError as e:
            logging.warning("[IMUSensor] os error", e)

    def get_data(self):
        """
        Get the full data
        """
        return {
            'accel': self.accel,
            'gyro': self.gyro,
            'yaw': self.orientation['yaw']
        }
        
    def stop(self):
        logging.info("IMU Sensor: stopped")