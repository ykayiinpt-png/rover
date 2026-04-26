from datetime import datetime, timezone
import logging
import multiprocessing
import threading
import time

import numpy as np

from src.core.utils import clamp, dict_equal_fast, sign, wrap_angle
from src.raspberry.hardware.rover.motor import RMotor
from src.raspberry.hardware.rover.odometry import WheelOdometry
from src.raspberry.hardware.rover.pid import PIDController
from src.raspberry.hardware.sensors.imu import IMUSensor



class RoverYawEstimator:
    """
    Rover rotation around the z-axis estimator
    """
    
    def __init__(self, alpha=0.99, wheel_base=0.1):
        self.alpha = alpha
        
        # Cumulated theta along the running
        self.theta = 0.0
        self.wheel_base = wheel_base

    def update(self, gyro_z, d_left, d_right, dt):
        # IMU (intégration)
        theta_imu = self.theta + gyro_z * dt

        # Odométrie
        dtheta_odom = (d_right - d_left) / self.wheel_base
        theta_odom = self.theta + dtheta_odom
        
        print("Theta Odom", theta_odom, "Theta Imu", theta_imu, "dthetah_odom", dtheta_odom)

        # Fusion complémentaire
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
    
    def __init__(self,
                shared_state: dict,
                odo: WheelOdometry,
                imu: IMUSensor,
                imu_sensor_thread_lock: threading.Lock,
                pins_left, pins_right,
                pid_left, pid_right,
                pid_angle,
                theta_ref,
                pwm_bais_left=20, pwm_bais_right=20,
                wheel_base_width=0.10,
                active_pid=False,
                velocity=0.5, no_pid_speed=50):
        self.shared_state = shared_state
        self.imu = imu
        self.imu_sensor_thread_lock = imu_sensor_thread_lock
        self.odo = odo
        
        # pins_left = {'pwm': 12, 'dir': 24}
        self.motor_l = RMotor(pins_left['pwm'], pins_left['in1_pin'], pins_left['in2_pin'])
        self.motor_r = RMotor(pins_right['pwm'], pins_right['in1_pin'], pins_right['in2_pin'])
        
        self.active_pid = active_pid
        
        # In void to have 0.3m/s
        #self.pid_l = PIDController(10.0, 1.9, 0.1)
        #self.pid_r = PIDController(10.0, 1.9, 0.0)
        if pid_left is not None and pid_right is not None:
            self.pid_l = PIDController("Left", pid_left["P"], pid_left["I"], pid_left["D"], error_min=1, reset_integral=False)
            self.pid_r = PIDController("Right", pid_right["P"], pid_right["I"], pid_right["D"], error_min=1, reset_integral=False)
            
        
        self.pid_angle = PIDController("Angle", pid_angle["P"], pid_angle["I"], pid_angle["D"], error_min=1, reset_integral=True)
        self.yaw_estimator = RoverYawEstimator()
        self.theta_ref = theta_ref
        self.command_theta = 0.0
        
        self.velocity = velocity
        self.no_pid_speed = no_pid_speed
        self.target_v_l = self.velocity
        self.target_v_r = self.velocity
        self.command_v_l = 0.0
        self.command_v_r = 0.0
        self.pwm_l = 0.0
        self.pwm_r = 0.0
        self.pwm_bais_l = pwm_bais_left
        self.pwm_bais_r = pwm_bais_right
        self.pid_last_compute_time = None
        self.last_command = None
        self._stopped = False
        self.update_cycle_counter = 0
        
        # The command locker, no command has been locked
        self.target_v_lock =  {
            "n_cycles": 0,
            "active": False,
            "command": {}
        }
        self.stop_command = {"x": 0, "y": 0, "a": "stop"}
        
        self.wheel_base_width = wheel_base_width
        
        if not self.active_pid:
            logging.warning("[Robot Thread] Not active PID")

    @property        
    def target_linear(self):
        return (self.target_v_l + self.target_v_r )/2

    def move(self, linear, angular=0):
        """Set target velocity (m/s et rad/s)"""
        
        linear = max(min(linear, self.velocity), -self.velocity)
        
        self.target_v_l = (linear * 1) - (angular * self.wheel_base_width / 2)
        self.target_v_r = (linear * 1) + (angular * self.wheel_base_width / 2)
        
    def move_right(self, speed=0.5):
        """Tourne sur place vers la droite"""
        # Vitesse linéaire nulle, rotation négative
        self.move(0, -speed)
    
    def move_left(self, speed=0.5):
        """Tourne sur place vers la gauche"""
        # Vitesse linéaire nulle, rotation positive
        self.move(0, speed)
    
    def move_front(self, speed=0.3):
        """Avance tout droit"""
        # Vitesse linéaire positive, rotation nulle
        self.move(speed, 0)
    
    def move_back(self, speed=0.3):
        """Recule tout droit"""
        # Vitesse linéaire négative, rotation nulle
        self.move(-speed, 0)
        
    def move_break(self):
        """Arrêt d'urgence immédiat"""
        self.move(0, 0)
        # On force les PWM à 0 pour couper le couple moteur
        self.motor_l.set_speed(0)
        self.motor_r.set_speed(0)
        
        self._stopped = True
        
    def check_command(self):
        """
        Validates commands that will mofify the current movement
        of the robot
        """
        
        #print(self.shared_state)
        cmd = self.shared_state.get("remote_command", None)
        if cmd is None:
            return
        
        if self.last_command is None:
            if cmd.get("x") is not None:
                self.exec_command(cmd)
                self.last_command = cmd
        else:
            if not dict_equal_fast(cmd, self.last_command):
                if cmd["a"] == "stop":
                    self.exec_command(cmd)
                else:
                    self.change_direction(cmd)
            
    def change_direction(self, cmd):
        """
        Handle the direction change. If were going forward and a command said
        go back, we smooth to zero and then start rolling backward
        """
        
        if self.last_command is None:
            return
        
        # For the moment no need to reset the velocity
        #self.target_v_l = 0.01 * sign(self.target_v_l)
        #self.target_v_r = 0.01 * sign(self.target_v_r)
        
        
        
        # And we reset the error integral to avoid saturation
        # when we will restart the robot
        # [NOTE] By exprience no need to turn down the pid unless stopped
        #self.pid_l.interrupt()
        #self.pid_r.interrupt()
        
        self.odo.left_wheel.reset()
        self.odo.right_wheel.reset()
        #self.yaw_estimator.reset()
        
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
        
    def exec_command(self, cmd):
        """
        Apply the modification provoked by the new command
        that we have stored
        """
        if cmd["x"] == 1:
            self.target_v_l = abs(self.velocity)
            self.target_v_r = -abs(self.velocity)
            self._stopped = False
        elif cmd["x"] == -1:
            self.target_v_l = -abs(self.velocity)
            self.target_v_r = abs(self.velocity)
            self._stopped = False
        if cmd["y"] == 1:
            self.target_v_l = abs(self.velocity)
            self.target_v_r = abs(self.velocity)
            self._stopped = False
        elif cmd["y"] == -1:
            self.target_v_l = -abs(self.velocity)
            self.target_v_r = -abs(self.velocity)
            self._stopped = False
        elif cmd.get("a") == "stop":
            self.target_v_l = 0
            self.target_v_r = 0
            
            # And we reset the error integral to avoid saturation
            # when we will restart the robot
            self.pid_l.interrupt()
            self.pid_r.interrupt()
            self.pid_angle.interrupt()
            
            self.move_break()
            print("Stopped")
            
        
        print(f"\n\n\n Stopped: {self._stopped}")
            
        self.last_command = cmd
        
        
        
    def update(self, dt):
        """
        Boucle de contrôle appelée par le RobotController
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
        
        # 1. Obtenir les vitesses réelles via odométrie
        movement = self.odo.get_movement()
        dist_l = movement["left"]["dist"]
        dist_r = movement["right"]["dist"]
        #print("Dist_l", dist_l)
        #print("Dist_r", dist_r)
        
         # 0. On estime l'angle de rotation sur l'axe z
        imu_data = None
        with self.imu_sensor_thread_lock:
             imu_data = self.imu.get_data()
        
        #theta = self.yaw_estimator.update(
        #     gyro_z=imu_data[1]["z"],
        #     d_left=dist_l, d_right=dist_r,
        #     dt=dt
        #)
        
        
        theta = imu_data[2]
        self.command_theta = theta
        
        
        if self.last_command["y"] in [-1, 1]:
            theta_error = wrap_angle(self.theta_ref - theta, deg=True)
        else:
            theta_error = 0.0
        
        # We convert the error into degree in order to have
        # a margin when applying the PID Kp on the error
            
        #print("Theta: ", np.rad2deg(theta))
        omega = self.pid_angle.compute(self.theta_ref, theta, theta_error)
        print("Error theta: ", theta_error)
        print("Angle Omega: ", omega)
        omega = clamp(omega, -int(self.velocity * 0.2), int(self.velocity * 0.2))
        print("Angle Omega Clamped: ", omega)
        
        # Récupérer les vitesse avec l'odométrie
        self.command_v_l = movement["left"]["v"] #dist_l / dt
        self.command_v_r = movement["right"]["v"] #dist_r / dt
        
        # Mettre à jour les commande avec la vitesse angulaireS
        if self.last_command["y"] in [-1, 1]:
            # Because of the direction we choosesd on our board
            # normally in the right position as designed for the rover
            # left decrese and right increase
            self.target_v_l = self.velocity - omega
            self.target_v_r = self.velocity + omega
        else:
            pass
        
        # TODO: Check if command remains zero for at least 1s, if so reset the pid
        # TODO Check if the diff between the both velocity is similar duringt N Cycle
        # If not sililar, reset the motor to not move until we got a similar velocity
        
        if not self.active_pid:
            # Apply the same velocity
            self.motor_l.set_speed(self.no_pid_speed)
            self.motor_r.set_speed(self.no_pid_speed)
            return 

        if self._stopped:
            self.move_break()
            return
        
        # We compute PID here
        # 2. Calculer le PWM via PID
        #print(f"Targets: l={self.target_v_l} r={self.target_v_r}")
        #print(f"Command: l={self.command_v_l} r={self.command_v_r}")
        
        # Clamp Velocity
        # Important
        if abs(self.target_v_l - self.command_v_l > 1.5*self.velocity) or abs(self.target_v_r - self.command_v_l) > 1.5*self.velocity:
            #self.change_direction(self.stop_command)
            #time.sleep(1)
            #self.change_direction(self.last_command)
            print("Bobo")
            
            #return
        
        # Have to pass the absolute value of the target sign
        # since we can have negative value for velocity
        # and pid are optimized only for posiitive
        # The pwm will translate.
        # That why we have impose a tampred period to slow down to zero
        self.pwm_l = self.pid_l.compute(abs(self.target_v_l), self.command_v_l)
        self.pwm_r = self.pid_r.compute(abs(self.target_v_r), self.command_v_r)
        
        # 3. Compute the difference in velocity
        dv = self.command_v_l - self.command_v_r
        Kpwm = 0
        #print(f"dv={dv}, Kpwm={Kpwm}")
        
        self.pwm_l += self.pwm_bais_l - Kpwm
        self.pwm_r += self.pwm_bais_r + Kpwm
        
        
        self.motor_l.set_speed(self.pwm_l * sign(self.target_v_l))
        self.motor_r.set_speed(self.pwm_r * sign(self.target_v_r))
        
        # In case we have a target velock lock, we decrement and check if 
        # the required number of cycle has passed in order to execute
        # the holded command
        if self.target_v_lock["active"] == True:
            if self.target_v_lock["n_cycles"] > 0:
                self.target_v_lock["n_cycles"] = self.target_v_lock["n_cycles"] - 1
                #print("\n\nTarget Cycle remaining:", self.target_v_lock["n_cycles"], "\n\n\n")
            
                if self.target_v_lock["n_cycles"] == 0:
                    self.target_v_lock["active"] = False
                
                    # We execute the command that we was supposed to execute
                    self.exec_command(self.target_v_lock["command"])
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
            "wr_pid_e": self.rover.pid_r.prev_error,
            "wr_pid_i": self.rover.pid_r.integral,
            "wr_pid_d": self.rover.pid_r.prev_derivative,
            "wl_pid_e": self.rover.pid_l.prev_error,
            "wl_pid_i": self.rover.pid_l.integral,
            "wl_pid_d": self.rover.pid_l.prev_derivative,
            "th_t": self.rover.theta_ref,
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
            self.rover.check_command()
            
            
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
        
        