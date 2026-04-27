import logging
import multiprocessing
import random
import time
from datetime import datetime, timezone

class RaspberryPi:
    """
    Raspberry PI Object
    
    Implements 
    """
    
    def __init__(self, send_queue: multiprocessing.Queue, receive_queue: multiprocessing.Queue):
        self.send_queue = send_queue
        self.receive_queue = receive_queue
        
        self.stop_event = multiprocessing.Event()
    
    def run(self):
        while not self.stop_event.is_set():
            current_timestamp = datetime.now(timezone.utc).timestamp()
            # 1. Acquire data from GPIO
            # 2. Apply filters
            # 3. Push data to remote server (scheduling with queue)
            
            data = {
                "topic": "slam/sensors/data",
                "payload": {
                    # The start time of the data acquisition
                    "time": current_timestamp,
                    
                    # For each type or category of sensors we do have
                    # different acquition frequency. So the batch_dt
                    # the difference in secons between two acquisitions
                    # u is ofr ultration g is gyroscope
                    # It will be used in case we do have array
                    "batch_dt": {"u": 1},
                    # Ultrasound
                    "u_f": random.random() * 100,
                    "u_b": random.random() * 100,
                    "u_l": random.random() * 100,
                    "u_r": random.random() * 100,
                    
                    # IMU
                    
                    # Data
                }
            }
            
            try:
                self.send_queue.put(data, block=False)
                #print("Data put in queue")
            except Exception as e:
                logging.exception("[RaspBerry Pi] Error while sending data to queue")
            
            # 4. Computation
            # 5. read data from remote server (command, data, etc...)
            if not self.receive_queue.empty():
                remote_data = self.receive_queue.get()
                #print("Remote data: ", remote_data)
            # 6. Make decision
            #print("[RaspBerry Pi] Iteration done")
            time.sleep(1)
            
        logging.info("Raspberry PI main loop closed")
    
    def stop(self):
        logging.info("[RapberryPi] stop trigerred")
        self.stop_event.set()
    