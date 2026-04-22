from datetime import datetime, timezone
import logging
import multiprocessing
import threading
import time

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
        self.buffer_size = 10
        
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
        