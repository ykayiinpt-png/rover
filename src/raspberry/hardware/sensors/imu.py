import smbus2
import time
import math

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

    def _setup_sensor(self):
        """
        Init configuration 
        """
        # Exemple pour MPU-6050 : Sortir du mode veille
        self.bus.write_byte_data(self.address, 0x6B, 0)
        print(f"IMU {self.name} initialisée à l'adresse {hex(self.address)}")

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
        now = time.perf_counter()
        dt = now - self.last_update
        
        # Accelorometers - TODO: Read datacheet
        self.accel['x'] = self._read_raw_data(0x3B) / 16384.0
        self.accel['y'] = self._read_raw_data(0x3D) / 16384.0
        self.accel['z'] = self._read_raw_data(0x3F) / 16384.0

        # Gyroscope deg per second
        self.gyro['x'] = self._read_raw_data(0x43) / 131.0
        self.gyro['y'] = self._read_raw_data(0x45) / 131.0
        self.gyro['z'] = self._read_raw_data(0x47) / 131.0

        # z-axis rotation
        # Will help localization Filter
        self.orientation['yaw'] += self.gyro['z'] * dt
        
        self.last_update = now

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
        pass