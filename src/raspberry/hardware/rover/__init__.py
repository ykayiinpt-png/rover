from datetime import datetime, timezone
import logging
import multiprocessing
import threading
import time
from typing import Any

import numpy as np

from src.core.utils import clamp, dict_equal_fast, sign, wrap_angle
from src.raspberry.hardware.rover.motor import RMotor
from src.raspberry.hardware.rover.odometry import WheelOdometry
from src.raspberry.hardware.rover.pid import PIDController
from src.raspberry.hardware.sensors.imu import IMUSensor
from src.raspberry.navigation import Navigation



class RoverYawEstimator:
    """
    Estimate Rover rotation around the z-axis estimator
    with a complementary fusion filter that combines IMU value
    and odometry
    """
    
    def __init__(self, alpha=0.99, wheel_base=0.1):
        self.alpha = alpha
        
        # Cumulated theta along the running
        self.theta = 0.0
        self.wheel_base = wheel_base

    def update(self, gyro_z, d_left, d_right, dt):
        # IMU Integration (TODO: We will use value provided the IMUSensor directly)
        theta_imu = self.theta + gyro_z * dt

        # Odométrie
        dtheta_odom = (d_right - d_left) / self.wheel_base
        theta_odom = self.theta + dtheta_odom
        
        print("Theta Odom", theta_odom, "Theta Imu", theta_imu, "dthetah_odom", dtheta_odom)

        # Complementary fusion
        self.theta = self.alpha * theta_imu + (1 - self.alpha) * theta_odom
        self.theta = wrap_angle(self.theta)

        return self.theta
    
    def reset(self):
        self.theta = 0
        
    def stop(self):
        self.reset()
        self._stooped = True
    
class Rover:
    """
    Represents a physical rover with two wheels.
    
    It only handles commands move, right, left and back depending
    on a state: moving, stop, drifting. By doing that, it computes
    also the PID in order to make the wheels speed stable
    """
    
    MODE_MANUAL_NAVIGATION = 0
    MODE_AUTONOMOUS_NAVIGATION = 1
    MODE_WAYPOINTS_NAVIGATION = 2
    
    COMMAND_STOP = {"x": 0, "y": 0, "a": "stop"}
    COMMAND_FORWARD = {"x": 0, "y": 1, "a": "move"}
    COMMAND_BACKWARD = {"x": 0, "y": -1, "a": "move"}
    COMMAND_TURN_LEFT = {"x": -1, "y": 0, "a": "move"}
    COMMAND_TURN_RIGHT = {"x": 1, "y": 0, "a": "moves"}
    
    def __init__(self,
                shared_state: dict,
                shared_state_command_lock: Any, #multiprocessing.synchronize.Lock,
                odo: WheelOdometry,
                imu: IMUSensor,
                imu_sensor_thread_lock: threading.Lock,
                motor_left, motor_right,
                pid_motor_speed_left, pid_motor_speed_right,
                pid_angle,
                theta_target,
                control_mode: int,
                navigation: Navigation,
                pwm_bais_left=20, pwm_bais_right=20,
                wheels_base_distance=0.10,
                active_pid=False,
                active_angle_pid=False,
                base_velocity=50, base_rotation_velocity:int=0.1, no_pid_pwm_dutycycle_value=50):
        """
        :param theta_target: the angle to maintant aound the é-axis
        :param control_mode: defines how the rover is controlled. We do have
        the manual and the autonous
        :param wheels_base_distance: the distance that separate the left wheel
        and the right wheel
        :param base_rotation_velocity: Base angular velocity used for in-place rotations, expressed in degrees per second.
        """
        
        
        self.shared_state = shared_state
        self.shared_state_command_lock = shared_state_command_lock
        self.imu = imu
        self.imu_sensor_thread_lock = imu_sensor_thread_lock
        self.odo = odo
        self.wheels_base_distance = wheels_base_distance
        
        ######################################
        # Control mode
        self.control_mode = control_mode
        
        ###################################
        # Motors
        self.active_pid = active_pid
        self.active_angle_pid = active_angle_pid
        
        self.motor_l = RMotor(
            pwm_pin=motor_left['pwm_pin'], in1_pin=motor_left['in1_pin'], in2_pin=motor_left['in2_pin'],
            max_power=motor_left['max_power'], pwm=motor_left['pwm']
        )
        self.motor_r = RMotor(
            pwm_pin=motor_right['pwm_pin'], in1_pin=motor_right['in1_pin'], in2_pin=motor_right['in2_pin'],
            max_power=motor_right['max_power'], pwm=motor_right['pwm']
        )
        
        
        if pid_motor_speed_left is not None and pid_motor_speed_right is not None:
            self.pid_speed_l = PIDController("Left", 
                pid_motor_speed_left["P"], pid_motor_speed_left["I"], 
                pid_motor_speed_left["D"], error_min=1, reset_integral=False, 
                max_integral=pid_motor_speed_left["max_integral"])
            self.pid_speed_r = PIDController("Right",
                pid_motor_speed_right["P"], pid_motor_speed_right["I"], 
                pid_motor_speed_right["D"], error_min=1, reset_integral=False,
                max_integral=pid_motor_speed_right["max_integral"])
            
        ######################################
        # Straight line
        # Angle
        self.pid_angle = PIDController("Angle", pid_angle["P"], pid_angle["I"], pid_angle["D"], error_min=1, reset_integral=True)
        self.yaw_estimator = RoverYawEstimator()
        self.theta_target = theta_target
        self.command_theta = 0.0
        self.pid_angle_last_time = None
        
        ######################################
        # Speed
        # Velocity parameters
        """
        The bse velocy that wheels must maintain during running.
        It's expressed in RPM
        """
        self.base_velocity = base_velocity
        self.base_rotation_velocity = base_rotation_velocity
        self.no_pid_pwm_dutycycle_value = no_pid_pwm_dutycycle_value
        self.target_v_l = self.base_velocity
        self.target_v_r = self.base_velocity
        self.command_v_l = 0.0
        self.command_v_r = 0.0
        self.pwm_l = 0.0
        self.pwm_r = 0.0
        self.pwm_bais_l = pwm_bais_left
        self.pwm_bais_r = pwm_bais_right
        
        
        ############################################""
        # Command Section
        self.last_command = None
        self._stopped = False
        
        # The command locker, no command has been locked
        self.target_v_lock =  {
            "n_cycles": 0,
            "active": False,
            "command": {}
        }
        
        
        # Other conrols
        if not self.active_pid:
            logging.warning("[Robot Thread] Not active PID")
            
        #########################################
        # Navigation
        #
        self.navigation = navigation
            
    def set_theta_target(self, theta):
        """
        Set a new value as the theta target
        
        :param theta: the new target value
        """
        self.theta_target = theta
        

    @property        
    def target_linear(self):
        return (self.target_v_l + self.target_v_r )/2

    def move(self, linear, angular=0):
        """Set target base_velocity (m/s et rad/s)"""
        
        linear = max(min(linear, self.base_velocity), -self.base_velocity)
        
        self.target_v_l = (linear * 1) - (angular * self.wheels_base_distance / 2)
        self.target_v_r = (linear * 1) + (angular * self.wheels_base_distance / 2)
        
        
    def move_break(self):
        """Immediate stop"""
        self.move(0, 0)
        # On force les PWM à 0 pour couper le couple moteur
        self.motor_l.set_speed(0)
        self.motor_r.set_speed(0)
        
        self._stopped = True
    
    def is_equal_command(self, cmd_one, cmd_two):
        """
        Compare two commands and determine whether they are equivalent.

        :param cmd_one (dict): First command to compare.
        :param cmd_two (dict): Second command to compare.

        Returns:
            bool: True if both commands are equal, otherwise False.
        """
        
        return dict_equal_fast(cmd_one, cmd_two)
    
    def check_command(self, dt):
        """
        Validates commands that will mofify the current movement
        of the robot
        """
        
        cmd = self.shared_state.get("remote_command", None)
        if cmd is None:
            return
        
        if cmd.get("a") is None:
            return
        
        self.exec_command(cmd, dt)
            
    def change_direction(self, cmd):
        """
        Handle the direction change. If were going forward and a command said
        go back, we smooth to zero and then start rolling backward
        """
        
        if self.last_command is None:
            return
        
        self.odo.left_wheel.reset()
        self.odo.right_wheel.reset()
        self.yaw_estimator.reset()
        
        # We block any further change for a number of cycle
        self.target_v_lock =  {
            # Was the rover stopped before ? if yet use a smal cyle number
            "n_cycles": 1 if self._stopped else 10,
            "active": True,
            "command": cmd
        }
        
        # In any case deactivate the stop
        self._stopped = False
        
        # Hold the command
        self.last_command = cmd # TODO: We do not need anymore the command key inside the target_v_lock
        
    def exec_command(self, cmd, dt=None):
        """
        Apply the modification provoked by the new command
        that we have stored
        
        :param cmd: the command to execute
        :param dt: the rover update cycle duration
        """
        
        if dt is None:
            dt = 0
            
        self._stopped = False
        
        if cmd.get("x") == 1:
            self.theta_target -= self.base_rotation_velocity * dt
        elif cmd.get("x") == -1:
            self.theta_target += self.base_rotation_velocity * dt
        elif cmd.get("a") == "stop":
            self.target_v_l = 0
            self.target_v_r = 0
            
            # And we reset the error integral to avoid saturation
            # when we will restart the robot
            self.pid_speed_l.interrupt()
            self.pid_speed_r.interrupt()
            self.pid_angle.interrupt()
            self.odo.left_wheel.reset()
            self.odo.right_wheel.reset()
            self.target_v_l = 0
            self.target_v_r = 0
            self.pwm_l = 0
            self.pwm_r = 0
            
            self.move_break()
            logging.info("Stop command received")
            
        self.last_command = cmd
        
        # Clear the command
        with self.shared_state_command_lock:
            self.shared_state["remote_command"] = None
        
    def update(self, dt):
        """
        Main loop
        """        
        if self.last_command is None:
            print("No Command Yet received")
            return
        
        # If we already stopped, we just return
        if self._stopped:
            # Just to avoid, in case we voer do it without knowing
            # out for control
            # TODO: Find a way to fix this
            self.move_break()
            return
        
        if not self.active_pid:
            # Apply the same base_velocity
            self.motor_l.set_speed(self.no_pid_pwm_dutycycle_value)
            self.motor_r.set_speed(self.no_pid_pwm_dutycycle_value)
            return
        
        ##
        #  START DYNAMIC MOVE
        ##
        
        base_rpm = 0 #self.base_velocity
        now = time.perf_counter()
        
        ############################################
        # SENSORS DATA ACQUISITION
        #

        # Read the theta angle from the IMU SENSORS
        imu_data = None
        with self.imu_sensor_thread_lock:
             imu_data = self.imu.get_data()
        self.command_theta = imu_data[2]
        
        # TODO: Reactivate this later, because on long duration IMU lies
        #theta = self.yaw_estimator.update(
        #     gyro_z=imu_data[1]["z"],
        #     d_left=dist_l, d_right=dist_r,
        #     dt=dt
        #)
        
        # Read the odometry movement        
        movement = self.odo.get_movement()
        
        ############################################
        # Controls
        #
        
        theta_error = None
        
        # Waypoints Navigation control
        if self.control_mode == Rover.MODE_WAYPOINTS_NAVIGATION:
            theta_to_target, _distance, theta_error = self.navigation.get_target_heading(
                movement["avg_dist"], np.deg2rad(self.command_theta)
            )
            
            if theta_to_target is None:
                # We have reached the current waypoint target
                # so we stop
                base_rpm = 0
            else:
                #self.theta_target = theta_to_target
                
                if theta_error == 0:
                    # We are aligned with the target, so we move forward
                    self.last_command = Rover.COMMAND_FORWARD
                    base_rpm = self.base_velocity
                else:
                    # We have correction to do by rotate the rover in place
                    if theta_error > 0:
                        self.last_command = Rover.COMMAND_TURN_LEFT
                    elif theta_error < 0:
                        self.last_command = Rover.COMMAND_TURN_RIGHT
                    else:
                        pass
                    
                    base_rpm = 0
        elif self.control_mode == Rover.MODE_AUTONOMOUS_NAVIGATION:
            theta_error = wrap_angle(self.theta_target - self.command_theta, deg=True)
            pass
        elif self.control_mode == Rover.MODE_MANUAL_NAVIGATION:
            theta_error = wrap_angle(self.theta_target - self.command_theta, deg=True)
            pass
        else:
            pass
            
        #################################
        # PID angle
        #
        omega = 0
        if self.active_angle_pid:
            if self.pid_angle_last_time is None:
                self.pid_angle_last_time = now
            else:
                if theta_error < 20:
                    # We have to wait some time
                    # so that the velocity can stabilize
                    if now - self.pid_angle_last_time >= 1:
                        omega = self.pid_angle.compute(self.theta_target, self.command_theta, theta_error)
                        print("Error theta: ", theta_error)
                        print("Angle Omega: ", omega)
                        omega = clamp(omega, -int(self.base_velocity * 0.7), int(self.base_velocity * 0.7))
                        print("Angle Omega Clamped: ", omega)
                else:
                    omega = 5 if theta_error > 0 else -5
        
        ############################################
        # Odometry
        #        
        self.command_v_l = movement["left"]["v"]
        self.command_v_r = movement["right"]["v"]
        
        ############################################
        # Velocity target control
        #        
        # Update the target velocity
        if self.last_command["y"] == 1:
            self.target_v_l = base_rpm + omega
            self.target_v_r = base_rpm - omega
        elif self.last_command["y"] == -1:
            # Sign are inversed here because we are running backward
            self.target_v_l = base_rpm - omega
            self.target_v_r = base_rpm + omega
        else:
            pass 
        
        # Clamp base_Velocity
        # Important
        if abs(self.target_v_l - self.command_v_l > 1.5*self.base_velocity) or abs(self.target_v_r - self.command_v_l) > 1.5*self.base_velocity:
            pass
        
        #############################################
        # Motor PID 
        #
        # out the pwm dutycycle 
        self.pwm_l = self.pid_speed_l.compute(abs(self.target_v_l), self.command_v_l)
        self.pwm_r = self.pid_speed_r.compute(abs(self.target_v_r), self.command_v_r)
        
        # Velocity asjustment value, currently not needed
        # TODO: Remove it
        Kpwm = 0
        
        self.pwm_l += self.pwm_bais_l - Kpwm
        self.pwm_r += self.pwm_bais_r + Kpwm
        
        
        # Apply the the pid out value depending on the command direction
        # we have 
        
        # if self.last_command["y"] == 1:
        #     # Moving forward the default action
        #     pass
        # elif self.last_command["y"] == -1:
        #     # Move backward
        #     self.pwm_l = self.pwm_l * (-1)
        #     self.pwm_r = self.pwm_r * (-1)
        
        # Set motor speed
        self.motor_l.set_speed(self.pwm_l * sign(self.target_v_l))
        self.motor_r.set_speed(self.pwm_r * sign(self.target_v_r))
        print(self.pwm_r)
        
        #############################
        # Command changing tampering
        #
        # In case we have a target velock lock, we decrement and check if 
        # the required number of cycle has passed in order to execute
        # the holded command
        if self.target_v_lock["active"] == True:
            if self.target_v_lock["n_cycles"] > 0:
                self.target_v_lock["n_cycles"] = self.target_v_lock["n_cycles"] - 1
            
            if self.target_v_lock["n_cycles"] == 0:
                self.target_v_lock["active"] = False
                if self.target_v_lock["command"] is not None:
                    # We execute the command that we was supposed to execute
                    self.exec_command(self.target_v_lock["command"], dt)
                    self.target_v_lock["command"] = None
        
    def stop(self):
        self.motor_l.stop()
        self.motor_r.stop()
        
        if self.odo:
            self.odo.stop()
        
        logging.info("[Rover] Rover stopped")
        

class RoverThread(threading.Thread):
    def __init__(self, rover: Rover, odometry_data_sent_queue: multiprocessing.Queue,
                f=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.rover = rover
        self.f = f
        
        self.stop_event = threading.Event()
        self.daemon = True
        
        self.odometry_data_sent_queue = odometry_data_sent_queue
        
        self.buffer = []
        self.buffer_size = 5
        
    def handle_batch(self):
        """
        Compose batch data for the remote server
        """
        
        data = {
            "wl_t": self.rover.target_v_l,
            "wl_c": self.rover.command_v_l * sign(self.rover.target_v_l),
            "wr_t": self.rover.target_v_r,
            "wr_c": self.rover.command_v_r * sign(self.rover.target_v_r),
            "wl_p": abs(self.rover.pwm_l),
            "wr_p": abs(self.rover.pwm_r),
            "wr_pid_e": self.rover.pid_speed_r.prev_error,
            "wr_pid_i": self.rover.pid_speed_r.integral,
            "wr_pid_d": self.rover.pid_speed_r.prev_derivative,
            "wl_pid_e": self.rover.pid_speed_l.prev_error,
            "wl_pid_i": self.rover.pid_speed_l.integral,
            "wl_pid_d": self.rover.pid_speed_l.prev_derivative,
            "th_t": self.rover.theta_target,
            "th_c": self.rover.command_theta,
            "th_pid_e": self.rover.pid_angle.prev_error,
            "th_pid_i": self.rover.pid_angle.integral,
            "th_pid_d": self.rover.pid_angle.prev_derivative,
        }
        
        self.buffer.append(data)
        if len(self.buffer) == self.buffer_size:
            current_timestamp = datetime.now(timezone.utc).timestamp()
            
            # TODO: can do better here
            data = {
                "topic": "slam/rover/data/odometry",
                "payload": {
                    "time": current_timestamp,
                    "batch_dt": { "ax": 0.1},
                    # Ultrasound
                    "wl_t": [m['wl_t'] for m in self.buffer],
                    "wl_c": [m['wl_c'] for m in self.buffer],
                    "wr_t": [m['wr_t'] for m in self.buffer],
                    "wr_c": [m['wr_c'] for m in self.buffer],
                    "wl_p": [m['wl_p'] for m in self.buffer],
                    "wr_p": [m['wr_p'] for m in self.buffer],
                    "wr_pid_e": [m['wr_pid_e'] for m in self.buffer],
                    "wr_pid_i": [m['wr_pid_i'] for m in self.buffer],
                    "wr_pid_d": [m['wr_pid_d'] for m in self.buffer],
                    "wl_pid_e": [m['wl_pid_e'] for m in self.buffer],
                    "wl_pid_i": [m['wl_pid_i'] for m in self.buffer],
                    "wl_pid_d": [m['wl_pid_d'] for m in self.buffer],
                    "th_t": [m['th_t'] for m in self.buffer],
                    "th_c": [m['th_c'] for m in self.buffer],
                    "th_pid_e": [m['th_pid_e'] for m in self.buffer],
                    "th_pid_i": [m['th_pid_i'] for m in self.buffer],
                    "th_pid_d": [m['th_pid_d'] for m in self.buffer],
                }
            }
            
            # Clear the buffer and send the data
            self.buffer.clear()
            try:
                self.odometry_data_sent_queue.put_nowait(data)
            except Exception:
                pass
        
    def run(self):
        """
        
        """
        cycle_duration = 1/self.f
        last_handle_batch_time = time.perf_counter()
        
        while not self.stop_event.is_set():
            now = time.perf_counter()
            
            # Chek if we do have new command, It quiltely fast
            self.rover.check_command(dt=cycle_duration)
            
            
            start = time.perf_counter()
            # Call the rover to do an update internally
            self.rover.update(cycle_duration)
            
            # Handle Batch data
            if now - last_handle_batch_time > 0.1:
                self.handle_batch()
                last_handle_batch_time = now
                
            # Compute the waiting time
            update_duration = time.perf_counter() - start
            wait_duration = cycle_duration - update_duration
            if wait_duration > 0:
                time.sleep(wait_duration)
            else:
                logging.warning(f"Compute Too Long: excess_time={wait_duration}s")
        
        logging.info("[RoverThread] Loop finished")
        
    def shutdown(self):
        self.stop_event.set()
        logging.info("[RoverThread] Has set stop Event")
        self.rover.stop()
        logging.info("[RoverThread] Rover stopped")
        
        