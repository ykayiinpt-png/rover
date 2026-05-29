import random
import time

import numpy as np

from src.core.shared import MemorySharedDict
from src.core.utils import wrap_angle
from src.raspberry.exploration.openarea import OpenAreaExplorer


class ExplorationPlanner:
    """
    Manges the autonomous behavoir of the rover to avoid
    obstacle and define the suitable direction to tacke in order to 
    move freely
    """
    
    STATE_NONE = -1
    STATE_MOVE_FORWARD = 0
    STATE_ROTATE = 1
    STATE_STOP = 2
    STATE_OBSTACLE_DETECTED = 3
    STATE_OBSTACLE_AVOIDING = 4
    STATE_OBSTACLE_AVOIDING_ROTATE = 5
    STATE_WAIT_AFTER_STOP = 6

    def __init__(self,
                rover_shared_state: MemorySharedDict, 
                mapping_shared_state: MemorySharedDict,
                navigation_shared_state: MemorySharedDict,
                safe_distance=0.5,
                safe_avoid_angle=3,
                max_angle_gap_deg=50, min_sector_size_deg=60):
        """
        Instaciate the planner object
        
        :param safe_distance: the safe distance around the rover. Unit is meter
        :param safe_avoid_angle: define the threashold to accept as error between 
        the current heading angle and the target heading angle when avoiding
        obstacle by rotation. Unit is degree
        """
        
        self.rover_shared_state = rover_shared_state
        self.mapping_shared_state = mapping_shared_state
        self.navigation_shared_state = navigation_shared_state
        
        self.safe_distance = safe_distance
        self.safe_avoid_angle = safe_avoid_angle
        self.theta_target = 0.0
        
        # By default we stop
        # We have to move only if we have enough information about the
        # environment that the way is free to move
        self.state = ExplorationPlanner.STATE_NONE
        
        # open area explorer 
        self.open_area_explorer = OpenAreaExplorer(
            open_distance_threshold=self.safe_distance,
            filter_window_size=2,
            max_angle_gap_deg=max_angle_gap_deg,
            min_sector_size_deg=min_sector_size_deg,
        )
        self.rotate_total_theta_angle = 0
        self.rotate_prev_theta_angle = 0
        
        self._stopped = False
        self.detect_obstacle_top_time = time.perf_counter()
        

    def check_safe_zone(self) -> bool:
        """
        Check whether an obstacle is present inside the rover safety zone.

        This method only performs sensor evaluation and does NOT modify the
        planner state. State transitions must be handled by the FSM/controller.

        Returns:
            bool:
                True if an obstacle is detected in front of the rover,
                otherwise False.
        """

        # Ignore detection while rover is stopped
        if self._stopped:
            return False

        # Retrieve shared sensor data
        imu_data = self.mapping_shared_state.get("imu")
        odometry_data = self.mapping_shared_state.get("odometry")
        ultra_sound_dists = self.mapping_shared_state.get("ultra_sound_dists")
        ultra_sound_angle_offsets = self.mapping_shared_state.get(
            "ultra_sound_angle_offsets"
        )

        # Ensure all required data is available
        if any(
            data is None
            for data in (
                imu_data,
                odometry_data,
                ultra_sound_dists,
                ultra_sound_angle_offsets,
            )
        ):
            return False

        # Front ultrasonic sensor distance
        front_distance = ultra_sound_dists.get("u_f")

        if front_distance is None:
            return False

        print(f"Front obstacle distance: {front_distance:.2f} m: Obstacle: {front_distance < self.safe_distance}")

        # Obstacle detected inside safety range
        return front_distance < self.safe_distance

    def compute_safe_direction(self):
        """
        Compute the optimal angle that allows the rover to go far from the current
        detected obstacle using the distances from the four ultrasounds
        
        :param distances dict[str, float]: ultrasounds mesaured distances. keys are
        'u_f', 'u_b', 'u_l', 'u_r' 
        :return: heading angle in degree
        """
        # x, and y component of the differential vecteor
        # Our rover has it length aligned on the x axis of the IMU
        # so this change a little bit that a normal coordinate
        distances =  self.mapping_shared_state.get("ultra_sound_dists")
        #fx = distances['u_f'] - distances['u_b']
        #fy = distances['u_r'] - distances['u_l']
        u_f = distances.get('u_f', 0)
        u_b = distances.get('u_b', 0)
        u_l = distances.get('u_l', 0)
        u_r = distances.get('u_r', 0)

        # Heading angle most free
        #angle = wrap_angle(np.rad2deg(np.atan2(fy, fx)), deg=True)
        
        theta = None
        if (
            u_f < self.safe_distance and
            u_b < self.safe_distance and
            u_l < self.safe_distance and
            u_r < self.safe_distance
        ):
            return None
            
        # --------------------------------------------------
        # BEST DIRECTION SELECTION
        # --------------------------------------------------
        directions = {
            180: u_f,
            0: u_b,
            -90: u_l,
            90: u_r
        }

        best_angle = max(directions, key=directions.get)
        return best_angle
        
        
        angle = self.smooth_angle(
            self.theta_target,
            best_angle,
            alpha=0.1
        )
        return wrap_angle(angle + 2*self.safe_avoid_angle + random.randint(45, 90), deg=True)
    

    def smooth_angle(self, prev_angle, new_angle, alpha=0.3):
        """
        Circular exponential smoothing for angles in degrees.

        Keeps continuity across wrap-around (-180° / 180° boundary).

        Args:
            prev_angle (float): previous filtered angle (deg)
            new_angle (float): new measurement (deg)
            alpha (float): smoothing factor [0..1]
                        (higher = more reactive)

        Returns:
            float: smoothed angle in degrees
        """

        # convert to radians
        prev = np.deg2rad(prev_angle)
        new = np.deg2rad(new_angle)

        # convert to unit vectors
        prev_x, prev_y = np.cos(prev), np.sin(prev)
        new_x, new_y = np.cos(new), np.sin(new)

        # exponential smoothing in vector space
        x = (1 - alpha) * prev_x + alpha * new_x
        y = (1 - alpha) * prev_y + alpha * new_y

        # back to angle
        smoothed = np.rad2deg(np.arctan2(y, x))

        return smoothed

    def handle_obstacle(self, current_heading_angle):
        """
        Détermine l'orientation sécurisée et commande le rover pour éviter l'obstacle.
        
        :param current_heading_angle (float): the current heading angle in degree
        
        :return (tuple): the theta target to reach and the error from the current orientation 
        angle and the target angle that will get the rover far from the obstacle
        """
        
        theta_error = self.theta_target - current_heading_angle
        theta_error = wrap_angle(theta_error, deg=True)

        print(f"Explorer state: {self.state}")
        print(f"Theta target: {self.theta_target}")

        # -----------------------------------------
        # We are aligned with safe direction
        # -----------------------------------------
        if abs(theta_error) < self.safe_avoid_angle:

            theta_error = 0.0

            # we are aligned with safe direction
            self.theta_target = 0.0

            return current_heading_angle, theta_error, True

        # -----------------------------------------
        # Still rotating to find safe direction
        # -----------------------------------------
        return self.theta_target, theta_error, False
    
    def reset_search_area(self):
        self.rotate_total_theta_angle = 0
        self.rotate_prev_theta_angle = 0
        
        self.open_area_explorer.clear()
    
    def search_open_area(self, current_heading_angle):
        """
        Search for open area. We rotate for 360 degree and take samples
        As soon as we have aa complete tour done, with the samples
        we compute the best heading angle to take in order to avoid the
        current obstacle
        """
        delta = current_heading_angle - self.rotate_prev_theta_angle
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360
        
        self.rotate_total_theta_angle += delta
        self.rotate_prev_theta_angle = current_heading_angle
        
        print("Total Angle Rotation: ", self.rotate_total_theta_angle)
        
        if abs(self.rotate_total_theta_angle) > 360:
            # We have done a complete tour
            print("A complete tour done")
            
            best_angle = self.open_area_explorer.get_best_heading()
            return best_angle, 0, True
        else:
            # Add a sample (angle, distance from the front ultrasound)
            distances =  self.mapping_shared_state.get("ultra_sound_dists")
            u_f = distances.get('u_f', 0)
            
            self.open_area_explorer.add_sample(
                np.deg2rad(current_heading_angle),
                front_distance=u_f
            )

        
        return None, 360, False
        
    def start(self):
        self._stopped = False
        self.state = ExplorationPlanner.STATE_STOP
        
    def stop(self):
        self._stopped = True