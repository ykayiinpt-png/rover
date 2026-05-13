import logging
import multiprocessing
import threading
import time
import numpy as np

from src.core.shared import MemorySharedDict
from src.raspberry.hardware.rover import Rover, RoverThread
from src.raspberry.hardware.sensors.imu import IMUSensor
from src.raspberry.hardware.sensors.ultrasound import UltrasoundSensorArray
from src.raspberry.hardware.thread import IMUThread, UltrasoundThread

class RaspberryPi:
    """
    Raspberry PI Object
    
    Implements 
    """
    
    def __init__(self, rover: Rover, sonars_arr_obj: UltrasoundSensorArray,
                imu: IMUSensor, imu_sensor_thread_lock: threading.Lock,
                ultrasound_data_sent_queue: multiprocessing.Queue,
                imu_data_send_queue: multiprocessing.Queue,
                odometry_data_sent_queue: multiprocessing.Queue,
                commands_send_queue: multiprocessing.Queue,
                commands_receive_queue: multiprocessing.Queue,
                map_data_send_queue: multiprocessing.Queue,
                
                rover_shared_state: MemorySharedDict, 
                mapping_shared_state: MemorySharedDict,
                navigation_shared_state: MemorySharedDict):
        
        #state
        self.rover_shared_state = rover_shared_state
        self.mapping_shared_state = mapping_shared_state
        self.navigation_shared_state = navigation_shared_state
        
        #Attrs
        self.sonars = sonars_arr_obj
        self.imu = imu
        
        # We assume that we have a square of 8m x 8m to map
        # TODO: later we will handle the over sizing
        self.square_size = 8.0
        
        # Threads
        self.ultra_sound_thread = UltrasoundThread(
            sonars_arr=sonars_arr_obj,
            send_queue=ultrasound_data_sent_queue
        )
        
        self.imu_thread = IMUThread(
            sensor_hw=imu,
            lock=imu_sensor_thread_lock,
            imu_data_send_queue=imu_data_send_queue,
            rover_shared_state=self.rover_shared_state, 
            mapping_shared_state=self.mapping_shared_state,
            navigation_shared_state=self.navigation_shared_state
        )
        
        self.rover_thread = RoverThread(
            rover=rover,
            odometry_data_sent_queue=odometry_data_sent_queue,
        )
        
        self.running = True

    def start_all(self):
        # Calibration obligatoire au démarrage (Robot immobile)
        self.imu.calibrate(samples=100)
        
        # Lancement des threads
        logging.info("[RaspberryPI] Démarrage de la boucle principale...")
        self.ultra_sound_thread.start()
        logging.info("[RaspberryPI] Robot Controller: Ultrasound thread started")
        self.imu_thread.start()
        logging.info("[RaspberryPI] Robot Controller: Imu thread has started")
        self.rover_thread.start()
        logging.info("[RaspberryPI] Robot Controller: Rover Thread thread started")
        
        #self.rover_thread.rover.move(0.5, 0)

    def run(self):
        self.start_all()
        
        # TODO: Not necessary, but We put it in order to
        # keep the main process running
        while self.running:
            time.sleep(10)
 
    def stop(self):
        self.running = False
        logging.info("[RaspberryPI] Set stop event")
        
        self.ultra_sound_thread.shutdown()
        self.ultra_sound_thread.join()
        
        self.imu_thread.shutdown()
        self.imu_thread.join()
        
        self.rover_thread.shutdown()
        self.rover_thread.join()
        
        logging.info("[RaspberryPI] Système arrêté proprement.")
    