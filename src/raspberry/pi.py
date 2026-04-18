import logging
import multiprocessing
import random
import time


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
            # 1. Acquire data from GPIO
            # 2. Apply filters
            # 3. Push data to remote server (scheduling with queue)
            
            data = {
                "topic": "slam/sensors/data",
                "payload": {
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
                print("Data put in queue")
            except Exception as e:
                logging.exception("[RaspBerry Pi] Error while sending data to queue")
            
            # 4. Computation
            # 5. read data from remote server (command, data, etc...)
            # 6. Make decision
            print("[RaspBerry Pi] Iteration done")
            time.sleep(1)
            
        logging.info("Raspberry PI main loop closed")
    
    def stop(self):
        logging.info("[RapberryPi] stop trigerred")
        self.stop_event.set()
    