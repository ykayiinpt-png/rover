from datetime import datetime, timezone
import logging
import multiprocessing
import time

import numpy as np

from src.core.shared import MemorySharedDict
from src.raspberry.mapping.grid import OccupancyMap
from src.raspberry.mapping.kalman import KalmanMapping


class MappingProcess(multiprocessing.Process):
    
    def __init__(self, 
                ekf: KalmanMapping,
                occupacy_grid: OccupancyMap,
                mapping_position_data_sent_queue: multiprocessing.Queue,
                rover_shared_state: MemorySharedDict, 
                mapping_shared_state: MemorySharedDict,
                navigation_shared_state: MemorySharedDict,
                *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rover_shared_state = rover_shared_state
        self.mapping_shared_state = mapping_shared_state
        self.navigation_shared_state = navigation_shared_state
        
        self.mapping_position_data_sent_queue = mapping_position_data_sent_queue
        
        self.ekf = ekf
        self.occupacy_grid = occupacy_grid
        
        self.stop_event = multiprocessing.Event()
        
        self.buffer = []
        self.buffer_size = 5
        self.last_batch_time = time.perf_counter()
        
    def handle_batch(self, x, y, theta):
        self.buffer.append((x, y, theta))
        #print("Handling Mapping Bath,\n\n\n\n\n\n")

        if len(self.buffer) == self.buffer_size:
            current_timestamp = datetime.now(timezone.utc).timestamp()
            q_data = {
                "topic": "slam/rover/data/mapping/state",
                "payload": {
                    "time": current_timestamp,
                    "batch_dt": { "ax": 0.05, "rot": 0.05 },
                    "x": [m[0] for m in self.buffer],
                    "y": [m[1] for m in self.buffer],
                    "theta": [m[2] for m in self.buffer]
                }
            }
            
            # Clear the buffer
            self.buffer.clear()
            
            try:
                self.mapping_position_data_sent_queue.put_nowait(q_data)
            except Exception:
                logging.exception("Error Sending Mapping Position data to remote")

    
    def run(self):
        try:
            last_t = time.perf_counter()
        
            while not self.stop_event.is_set():
                now = time.perf_counter()
                dt = now - last_t
                
                if self.rover_shared_state.get("stop") == False:
                
                    # On récupère la vitesse angulaire actuelle (même si elle change)
                    imu_data = self.mapping_shared_state.get("imu")
                    odometry_data = self.mapping_shared_state.get("odometry")
                    ultra_sound_dists = self.mapping_shared_state.get("ultra_sound_dists")
                    ultra_sound_angle_offsets = self.mapping_shared_state.get("ultra_sound_angle_offsets")
                    
                    #print("[Mapping Process] ", imu_data, odometry_data, ultra_sound_dists, ultra_sound_angle_offsets)
                    #print("[Mapping Process] ", self.mapping_shared_state, self.mapping_shared_state.get("odometry"))
                    if (imu_data is None) or (odometry_data is None) or (ultra_sound_angle_offsets is None) or (ultra_sound_dists is None):
                        continue
                    
                    #print("[Mapping Process] ", "Computing")
                    w = np.deg2rad(imu_data[1]["z"])
                    cumulated_yaw = np.deg2rad(imu_data[2])
                    v = odometry_data["avg_ms"]
                    #print(f"Aberage velocity: {v}")
                    
                    # Le dt ici est la clé : il lie la vitesse changeante au temps réel
                    self.ekf.predict(v, w, dt)
                    
                    # On corrige avec le Yaw absolu
                    self.ekf.update_yaw(cumulated_yaw)
                    
                    # Get the state
                    x, y, theta = self.ekf.get_state()
                    
                    
                    for k, v in ultra_sound_dists.items():
                        #print(f"Ulstra sound k: {k}  -- {v}")
                        self.occupacy_grid.mark_obstacle(
                            x, y, theta,
                            v,
                            ultra_sound_angle_offsets[k]
                        )
                        
                    if now - self.last_batch_time > 0.5:
                        self.handle_batch(x, y, theta)
                        self.last_batch_time = now
                else:
                    pass
                    #logging.info("[Mapping Process] Rover Stopped")
                
                last_t = now
                time.sleep(0.05) 
                
            logging.info("[MappingProcess] Stopped Loop")
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logging.exception("[MappingProcess] Exception")
        finally:
            pass
            #self.stop()
            
        
        
    def stop(self):
        logging.info("[MappingProcess] Stopping Process")
        self.stop_event.set()
        
        self.occupacy_grid.stop()