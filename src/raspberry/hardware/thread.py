from datetime import datetime, timezone
import logging
import multiprocessing
import threading
import time

from src.raspberry.hardware.sensors.imu import IMUSensor
from src.raspberry.hardware.sensors.ultrasound import UltrasoundSensorArray


class UltrasoundThread(threading.Thread):
    def __init__(self, sonars_arr: UltrasoundSensorArray,
                send_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.sonars = sonars_arr
        self.send_queue = send_queue
        
        self.daemon = True
        self.stop_event = threading.Event()
        
        self.buffer = []
        self.buffer_size = 20
        
    def run(self):
        while not self.stop_event.is_set():
            self.sonars.scan_sequence()
            self.buffer.append(self.sonars.last_scan_data)
            
            if len(self.buffer) == self.buffer_size:
                current_timestamp = datetime.now(timezone.utc).timestamp()
                data = {
                    "topic": "slam/sensors/data/ultrasound",
                    "payload": {
                        "time": current_timestamp,
                        "batch_dt": {"u": 0.00001 + 0.03 * 4},
                        # Ultrasound
                        "u_f": [m['u_f'] for m in self.buffer],
                        "u_b": [m['u_b'] for m in self.buffer],
                        "u_l": [m['u_l'] for m in self.buffer],
                        "u_r": [m['u_r'] for m in self.buffer],
                    }
                }
                
                # Clear the buffer
                self.buffer = []
                
                self.send_queue.put(data)
                
                print("\n\n\ Data sent")
                print(data)
            
            time.sleep(0.00001) # TODO: Necessary ?
            
        logging.info("Ultrasound Thread loop closed")
            
    def get_last_scan_data(self):
        return self.sonars.last_scan_data
    
    def shutdown(self):
        self.stop_event.set()
        logging.info("Ultrasound Thread shutting down")
        self.sonars.shutdown()
        logging.info("Ultrasound shutdown OK")
        
        
class IMUThread(threading.Thread):
    def __init__(self, sensor_hw: IMUSensor, imu_data_send_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensor = sensor_hw
        self.stop_event = threading.Event()
        
        self.imu_data_send_queue = imu_data_send_queue
        
        self.daemon = True
        
        # Données partagées
        self.yaw = 0.0
        self.accel_x = 0.0
        self.gyro_z = 0.0
        self.lock = threading.Lock()
        
        self.buffer = []
        self.buffer_size = 20

    def run(self):
        print("Run ImuThread")
        while not self.stop_event.is_set():       
            # Mise à jour des données brutes et calcul du Yaw
            self.sensor.update() 
            data = self.sensor.get_data()
            
            self.buffer.append(data)
            
            if len(self.buffer) == self.buffer_size:
                current_timestamp = datetime.now(timezone.utc).timestamp()
                q_data = {
                    "topic": "slam/sensors/data/imu",
                    "payload": {
                        "time": current_timestamp,
                        "batch_dt": { "ax": 0.01, "rot": 0.01 },
                        # Ultrasound
                        "rot": [m['yaw'] for m in self.buffer],
                        "a_x": [m['accel']['x'] for m in self.buffer],
                    }
                }
                
                # Clear the buffer
                self.buffer = []
                
                self.imu_data_send_queue.put(q_data)
                
                print("\n\n\ IMU Data sent")
                print(q_data)
            
            with self.lock:
                self.accel_x = data['accel']['x']
                self.gyro_z = data['gyro']['z']
                self.yaw = data['yaw']
            
            # On fait tourner l'IMU à 100Hz (très stable)
            time.sleep(0.01)

    def get_latest_data(self):
        with self.lock:
            return self.accel_x, self.gyro_z, self.yaw
        
    def shutdown(self):
        self.stop_event.set()
        logging.info("Imu Thread shutting down")
        self.sensor.stop()
        logging.info("Imu shutdown OK")
        