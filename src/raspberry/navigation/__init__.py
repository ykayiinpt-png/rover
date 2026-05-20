import collections
from datetime import datetime, timezone
import logging
import math
import multiprocessing
import queue
import time

import numpy as np

from src.core.utils import wrap_angle

class Navigation:
    """
    The Navigation class manages the rover's route by storing and organizing
    a sequence of waypoints that the rover must follow. It provides functionality 
    for tracking progress along the route, retrieving the next target waypoint, 
    and determining whether the rover has completed its path.
    """
    
    STATE_ROTATE = 0
    STATE_MOVE_FORWARD = 1
    STATE_STOP = 2
    
    def __init__(self, 
                 shared_state: dict,
                 map_data_sent_queue: multiprocessing.Queue,
                 dim_w: float, dim_l: float,
                dist_threshold:float =0.1, angle_threshold:float =5, distance_multiplier=2):
        """
        Initialize the Navigation object
        
        :param dist_threshold: Maximum error allowed on the distance compute 
        in order to reach target from the the list of the waypoints. It must in meter
        unit
        :param angle_threshold: under the threashold, we consider the rover well alogned
        to target so it can go forward. Over the threashold the rover mus must rotate to 
        ajust the headning target angle
        :param distance_multiplier: defines the the factor of multiplication we have to multiply the
        distance computed in order to match the distance in pysical world after running many experiment
        """
        
        self.shared_state = shared_state
        self.x, self.y = 0.0, 0.0
        
        self.waypoints = [(1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
        self.current_wp_idx = 0
        self.dist_threshold = dist_threshold
        self.angle_threshold = angle_threshold
        self.dim_w = dim_w
        self.dim_l = dim_l
        self.distance_multiplier = distance_multiplier
        
        # We start with a stop state
        self.state = Navigation.STATE_MOVE_FORWARD
        self.theta_to_target = 0.0
        self.distance_to_target = None
        # How much distznce we have traveled since the last waypoint 
        self.distance_from_last_target = 0
        self.started = False
        
        self.last_batch_time = time.perf_counter()
        self.cumul_distance = 0.0
        
        self.buffer = []
        self.buffer_size = 5
        
        self.map_data_sent_queue = map_data_sent_queue
        
    def set_waypoints(self, waypoints: list, contains_start=False):
        """
        Set the navigation route for the rover.

        Replaces the current list of waypoints with a new ordered
        collection of target positions that the rover must follow.

        :param waypoints (list): Ordered list of waypoints defining
        the rover's path.
        :param dist_threshold (float): the maximum distance error allowed around the target point
        """
        
        if not contains_start:
            self.waypoints = [[0, 0]]
            
            self.x = 0
            self.y = 0
        else:
            self.waypoints = []
            
        # TODO: Pay attention
        self.waypoints.extend([[self.dim_l * x, self.dim_w * y] for x,y in waypoints])
        #print(self.waypoints)
            
        self.x, self.y = self.waypoints[0][0], self.waypoints[0][1] 
        
        
        
        
        # Set the theta to target back to 0.0
        self.theta_to_target = 0.0
        self.theta_next_list = []
        self.distance_from_last_target = 0
        self.current_wp_idx = 1
        self.started = True
        
        self.buffer.clear()
        
        print("Set started:")
        
    def handle_batch(self):
        self.buffer.append((self.x, self.y, self.cumul_distance))
        #print("Handling Bath,\n\n\n\n\n\n")

        if len(self.buffer) == self.buffer_size:
            current_timestamp = datetime.now(timezone.utc).timestamp()
            q_data = {
                "topic": "slam/rover/data/navigation/position",
                "payload": {
                    "time": current_timestamp,
                    "batch_dt": { "ax": 0.05, "rot": 0.05 },
                    "x": [m[0] for m in self.buffer],
                    "y": [m[1] for m in self.buffer],
                    "dist": [m[2] for m in self.buffer]
                }
            }
            
            # Clear the buffer
            self.buffer.clear()
            
            try:
                self.map_data_sent_queue.put_nowait(q_data)
            except Exception:
                logging.exception("Error Sending Navigation data to remote")

        

    def get_target_heading(self, d_moy: float, current_angle: float):
        """
        Update the rover's current position using the traveled distance
        and current orientation angle.. It Computes the the target heading angle from the current position
        to the target position
        
        :param d_moy (float): Average distance traveled by the rover.
        :param current_angle_rad (float): Current rover heading angle in degree.
        :return (tuple):
            - theta_to_target: the target heading angl
            - distance: the remaining distance
            - theta_error: heading angle error from the crr
        """
        if not self.started:
            return None, None, None
        
        
        
        now = time.perf_counter()
        
        if self.current_wp_idx >= len(self.waypoints):
            # We stop because we do not have any further waypoint to reach
            self.state = Navigation.STATE_STOP
            #print("Thetas plus: ", self.theta_next_list)
            
            return None, 0, 0
        
        d_moy = self.shared_state["odometry"]["avg_dist"]
        print("[Navigation]: d_moy from Shared object:", d_moy)
        
        current_angle_rad = np.deg2rad(current_angle)
        
        self.x += d_moy * math.cos(current_angle_rad)
        self.y += d_moy * math.sin(current_angle_rad)
        
        self.cumul_distance += d_moy
        
        
        target_x, target_y = self.waypoints[self.current_wp_idx]
        
        dx = target_x - self.x
        dy = target_y - self.y
        
        distance = math.sqrt(dx**2 + dy**2)
        #theta_to_target = math.degrees(math.atan2(dy, dx))            
            
        if self.distance_to_target == None:
            target_x, target_y = self.waypoints[self.current_wp_idx]
            target_x_1, target_y_1 = self.waypoints[self.current_wp_idx-1]
        
            self.distance_to_target = math.sqrt((target_x - target_x_1)**2 + (target_y - target_y_1)**2)
            
            # Heading angle to the next target
            next_angle = wrap_angle(math.degrees(
                math.atan2(target_y - target_y_1, target_x - target_x_1)
            ), deg=True)
            
            # TODO: Rewrite those lines
            
            
            #print("new angle: ", next_angle)
            #print("Theta Target before: ", self.theta_to_target)
            self.theta_to_target = next_angle
            self.theta_to_target = wrap_angle(self.theta_to_target, deg=True)
            
            #self.theta_next_list.append({"na": next_angle, "th": self.theta_to_target})
            # TODO: multiply the distance by two, real experience eveal that
            # travel distance is the command distance divided by two
            #print(f"Distance to next target: {self.distance_to_target}")
            
        # Normaly it has to be - 
        # But we have inversed the axis Of ou our base
        # Pay attention using the real word income
        theta_error = wrap_angle(self.theta_to_target - current_angle, deg=True)
        print("Theta Error Navigation: ", theta_error)
        print("d_moy:", d_moy)
        print("Theta to target: ", self.theta_to_target)
        print(f"Current angle: {current_angle}")
        #print("Distance to Target: ", distance)
        print(f"Distance from last target: {self.distance_from_last_target}")
        #print(f"State: {self.state}")
        
        
        # Check if we have to do a rotation before start moving
        # If we were at stop position and have waypoint to reach we check
        # if we had to rotate     
        if (self.state == Navigation.STATE_ROTATE) or \
            (self.state == Navigation.STATE_STOP and self.current_wp_idx < len(self.waypoints)):
            # Only check the angle if we have to rotate
            if abs(theta_error) < self.angle_threshold:
                #print("Theta reached")
                theta_error = 0
                
                # We start Moving Forward
                self.state = Navigation.STATE_MOVE_FORWARD
            else:
                self.state = Navigation.STATE_ROTATE
                
        elif self.state == Navigation.STATE_MOVE_FORWARD:
            self.distance_from_last_target += d_moy
            
            if abs(self.distance_to_target - self.distance_from_last_target * self.distance_multiplier) < self.dist_threshold:
                self.current_wp_idx += 1
                ##print(f"Waypoint {self.current_wp_idx} reached !")
                
                self.state = Navigation.STATE_STOP
                self.distance_to_target = None
                self.distance_from_last_target = 0.0
            
        if now - self.last_batch_time > 0.5:
            self.handle_batch()
            self.last_batch_time = now
            
        return self.theta_to_target, distance, theta_error
    
    def stop(self):
        pass
