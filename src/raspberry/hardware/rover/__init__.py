from datetime import datetime, timezone
import logging
import multiprocessing
import threading
import time

from src.core.utils import dict_equal_fast, sign
from src.raspberry.hardware.rover.motor import RMotor
from src.raspberry.hardware.rover.odometry import WheelOdometry
from src.raspberry.hardware.rover.pid import PIDController


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
                pins_left, pins_right,
                pid_left, pid_right,
                pwm_bais_left=20, pwm_bais_right=20,
                wheel_base_width=0.10,
                active_pid=False,
                velocity=0.5, no_pid_speed=50):
        self.shared_state = shared_state
        # pins_left = {'pwm': 12, 'dir': 24}
        self.motor_l = RMotor(pins_left['pwm'], pins_left['in1_pin'], pins_left['in2_pin'])
        self.motor_r = RMotor(pins_right['pwm'], pins_right['in1_pin'], pins_right['in2_pin'])
        self.odo = odo
        
        self.active_pid = active_pid
        
        # In void to have 0.3m/s
        #self.pid_l = PIDController(10.0, 1.9, 0.1)
        #self.pid_r = PIDController(10.0, 1.9, 0.0)
        if pid_left is not None and pid_right is not None:
            self.pid_l = PIDController("Left", pid_left["P"], pid_left["I"], pid_left["D"])
            self.pid_r = PIDController("Right", pid_right["P"], pid_right["I"], pid_right["D"])
        
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
        
        # The command locker, no command has been locked
        self.target_v_lock =  {
            "n_cycles": 0,
            "active": False,
            "command": {}
        }
        
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
        
        print(self.shared_state)
        cmd = self.shared_state.get("remote_command", None)
        if cmd is None:
            return
        
        if self.last_command is None:
            if cmd.get("x") is not None:
                self.exec_command(cmd)
                self.last_command = cmd
        else:
            if not dict_equal_fast(cmd, self.last_command):
                self.change_direction(cmd)
            
    def change_direction(self, cmd):
        """
        Handle the direction change. If were going forward and a command said
        go back, we smooth to zero and then start rolling backward
        """
        
        if self.last_command is None:
            return
        
        self.target_v_l = 0.01 * sign(self.target_v_l)
        self.target_v_r = 0.01 * sign(self.target_v_r)
        
        
        
        # And we reset the error integral to avoid saturation
        # when we will restart the robot
        self.pid_l.interrupt()
        self.pid_r.interrupt()
        
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
            
            #self.move_break()
            print("Stopped")
            
        
        print(f"\n\n\n Stopped: {self._stopped}")
            
        self.last_command = cmd
        
        
        
    def update(self, dt):
        """
        Boucle de contrôle appelée par le RobotController
        """
        if dt <= 0.01:
            # We won't handle small time difference
            return 
        
        if self.last_command is None:
            print("No Command Yet received")
            return
        
        # 1. Obtenir les vitesses réelles via odométrie
        movement = self.odo.get_movement()
        dist_l = movement["left"]["dist"]
        dist_r = movement["right"]["dist"]
        print("Dist_l", dist_l)
        print("Dist_r", dist_r)
        
        self.command_v_l = dist_l / dt
        self.command_v_r = dist_r / dt
        
        # TODO: Check if command remains zero for at least 1s, if so reset the pid
        # TODO Check if the diff between the both velocity is similar duringt N Cycle
        # If not sililar, reset the motor to not move until we got a similar velocity
        
        if not self.active_pid:
            # Apply the same velocity
            self.motor_l.set_speed(self.no_pid_speed)
            self.motor_r.set_speed(self.no_pid_speed)
            return 

        if self._stopped:
            return
        
        # We compute PID here
        # 2. Calculer le PWM via PID
        print(f"Targets: l={self.target_v_l} r={self.target_v_r}")
        print(f"Command: l={self.command_v_l} r={self.command_v_r}")
        
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
        print(f"dv={dv}, Kpwm={Kpwm}")
        
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
                print("\n\nTarget Cycle remaining:", self.target_v_lock["n_cycles"], "\n\n\n")
                
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
    def __init__(self, rover: Rover, odometry_data_sent_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.rover = rover
        
        self.stop_event = threading.Event()
        self.daemon = True
        
        self.hz = 50 # Frequency of PID (20ms)
        self.odometry_data_sent_queue = odometry_data_sent_queue
        
        self.buffer = []
        self.buffer_size = 5
        
        self.loop_dt = 0.1 # 0.8 second
        
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
            "wr_p": abs(self.rover.pwm_r)
        }
        
        self.buffer.append(data)
        if len(self.buffer) == self.buffer_size:
            current_timestamp = datetime.now(timezone.utc).timestamp()
            data = {
                "topic": "slam/rover/data/odometry",
                "payload": {
                    "time": current_timestamp,
                    "batch_dt": { "ax": self.loop_dt},
                    # Ultrasound
                    "wl_t": [m['wl_t'] for m in self.buffer],
                    "wl_c": [m['wl_c'] for m in self.buffer],
                    "wr_t": [m['wr_t'] for m in self.buffer],
                    "wr_c": [m['wr_c'] for m in self.buffer],
                    "wl_p": [m['wl_p'] for m in self.buffer],
                    "wr_p": [m['wr_p'] for m in self.buffer],
                }
            }
            
            # Clear the buffer and send the data
            self.buffer.clear()
            self.odometry_data_sent_queue.put(data)
        
        
    def run(self):
        """Boucle haute fréquence du PID"""
        
        dt = 0
        dt_pid_end = None
        
        while not self.stop_event.is_set():
            self.rover.check_command()
            
            if dt_pid_end is not None:
                dt = time.perf_counter() - dt_pid_end
                print("PID waiting dt: ", dt)

            self.rover.update(dt)
            dt_pid_end = time.perf_counter()
                
            
            self.handle_batch()
            
            # Wait for the speed modification to have effect
            time.sleep(self.loop_dt)
        
        logging.info("[RoverThread] Loop finished")
        
    def shutdown(self):
        self.stop_event.set()
        logging.info("[RoverThread] Has set stop Event")
        self.rover.stop()
        logging.info("[RoverThread] Rover stopped")
        
        