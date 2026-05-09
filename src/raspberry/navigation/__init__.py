import collections
import math
import queue

from src.core.utils import wrap_angle

class Navigation:
    """
    The Navigation class manages the rover's route by storing and organizing
    a sequence of waypoints that the rover must follow. It provides functionality 
    for tracking progress along the route, retrieving the next target waypoint, 
    and determining whether the rover has completed its path.
    """
    
    def __init__(self, dist_threshold:float =0.1, angle_threshold:float =10):
        """
        Initialize the Navigation object
        
        :param dist_threshold: Maximum error allowed on the distance compute 
        in order to reach target from the the list of the waypoints. It must in meter
        unit
        :param angle_threshold: under the threashold, we consider the rover well alogned
        to target so it can go forward. Over the threashold the rover mus must rotate to 
        ajust the headning target angle
        """
        
        self.x, self.y = 0.0, 0.0
        
        self.waypoints = [(1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
        self.current_wp_idx = 0
        self.dist_threshold = dist_threshold
        self.angle_threshold = angle_threshold
        
    def set_waypoints(self, waypoints: list):
        """
        Set the navigation route for the rover.

        Replaces the current list of waypoints with a new ordered
        collection of target positions that the rover must follow.

        :param waypoints (list): Ordered list of waypoints defining
        the rover's path.
        :param dist_threshold (float): the maximum distance error allowed around the target point
        """
        self.waypoints = waypoints
        self.dist_threshold = self.dist_threshold
        
        self.x = 0
        self.y = 0
        

    def get_target_heading(self, d_moy: float, current_angle_rad: float):
        """
        Update the rover's current position using the traveled distance
        and current orientation angle.. It Computes the the target heading angle from the current position
        to the target position
        
        :param d_moy (float): Average distance traveled by the rover.
        :param current_angle_rad (float): Current rover heading angle in radians.
        :return (tuple):
            - theta_to_target: the target heading angl
            - distance: the remaining distance
            - theta_error: heading angle error from the crr
        """
        
        if self.current_wp_idx >= len(self.waypoints):
            return None, 0
        
        self.x += d_moy * math.cos(current_angle_rad)
        self.y += d_moy * math.sin(current_angle_rad)
        
        target_x, target_y = self.waypoints[self.current_wp_idx]
        
        dx = target_x - self.x
        dy = target_y - self.y
        
        distance = math.sqrt(dx**2 + dy**2)
        theta_to_target = math.degrees(math.atan2(dy, dx))
        
        # If we have reached the waypoint, we go to next
        if distance < self.dist_threshold:
            self.current_wp_idx += 1
            print(f"Waypoint {self.current_wp_idx} reached !")
            
        
        theta_error = wrap_angle(theta_to_target - current_angle_rad, deg=True)
        if abs(theta_error) < self.angle_threshold:
            theta_error = 0
            
        return theta_to_target, distance, theta_error
