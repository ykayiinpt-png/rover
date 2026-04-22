import logging
import threading
import time

from src.raspberry.hardware.sensors.ultrasound import UltrasoundSensorArray

class UltrasoundThread(threading.Thread):
    def __init__(self, sonars_arr: UltrasoundSensorArray, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.sonars = sonars_arr
        
        self.daemon = True
        self.stop_event = threading.Event()
        
    def run(self):
        while not self.stop_event.is_set():
            self.sonars.scan_sequence()
            
            time.sleep(0.00001) # TODO: Necessary ?
            
        logging.info("Ultrasound Thread loop closed")
            
    def get_last_scan_data(self):
        return self.sonars.last_scan_data
    
    def shutdown(self):
        self.stop_event.set()
        logging.info("Ultrasound Thread shutting down")
        self.sonars.shutdown()
        logging.info("Ultrasound shutdown OK")
        