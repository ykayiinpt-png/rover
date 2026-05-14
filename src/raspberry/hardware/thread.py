from datetime import datetime, timezone
import logging
import multiprocessing
import threading
import time

from src.core.shared import MemorySharedDict
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
                
                #print("\n\n\ Data sent")
                #print(data)
            
            time.sleep(0.01) # TODO: Necessary ?
            
        logging.info("Ultrasound Thread loop closed")
            
    def get_last_scan_data(self):
        return self.sonars.last_scan_data
    
    def shutdown(self):
        self.stop_event.set()
        logging.info("Ultrasound Thread shutting down")
        self.sonars.shutdown()
        logging.info("Ultrasound shutdown OK")
        
        
class IMUThread(threading.Thread):
    def __init__(self, sensor_hw: IMUSensor, imu_data_send_queue: multiprocessing.Queue,
                rover_shared_state: MemorySharedDict, 
                mapping_shared_state: MemorySharedDict,
                navigation_shared_state: MemorySharedDict,
                lock: threading.Lock, f=200,
                *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        
        self.rover_shared_state = rover_shared_state
        self.mapping_shared_state = mapping_shared_state
        self.navigation_shared_state = navigation_shared_state
        
        # Self attributes
        self.f = 200
        self.sensor = sensor_hw
        self.stop_event = threading.Event()
        self.imu_data_send_queue = imu_data_send_queue
        
        self.lock = lock
        
        self.buffer = []
        self.buffer_size = 20
        
    def handle_batch(self, data):
        self.buffer.append(data)

        if len(self.buffer) == self.buffer_size:
            current_timestamp = datetime.now(timezone.utc).timestamp()
            q_data = {
                "topic": "slam/sensors/data/imu",
                "payload": {
                    "time": current_timestamp,
                    "batch_dt": { "ax": 0.05, "rot": 0.05 },
                    # Ultrasound
                    # 2 -> yaw
                    "theta": [m[2] for m in self.buffer],
                    # 1 -> gyrao data
                    "g_z": [m[1]['z'] for m in self.buffer],
                }
            }
            
            # Clear the buffer
            self.buffer.clear()
            
            try:
                self.imu_data_send_queue.put_nowait(q_data)
            except Exception:
                logging.exception("Error Sending Imu data to rEMOTE")

    def run(self):
        delta_t = 1/self.f
        
        last_time = time.perf_counter()
        last_handle_batch_time = time.perf_counter()
        
        while not self.stop_event.is_set():
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            
            with self.lock:
                # The Imu class has an internal delta_t compute to integrate
                # angle
                self.sensor.update()
                
                imu_data = self.sensor.get_data()
                
                self.rover_shared_state["imu"] = imu_data
                self.mapping_shared_state["imu"] = imu_data
                self.navigation_shared_state["imu"] = imu_data
            
                # Handle Batch data
                if now - last_handle_batch_time > 0.05:
                    self.handle_batch(imu_data)
                    last_handle_batch_time = now
            

            time.sleep(delta_t)
        
    def shutdown(self):
        self.stop_event.set()
        try:
            time.sleep(5) # Wait some time to have the lopp ended
            self.lock.release()
            self.lock.release_lock()
        except:
            pass
        
        logging.info("Imu Thread shutting down")
        self.sensor.stop()
        logging.info("Imu shutdown OK")
        