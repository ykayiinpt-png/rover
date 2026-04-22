import logging
import threading
import time

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
    
    def __init__(self, odo: WheelOdometry, pins_left, pins_right, wheel_base_width=0.10,  active_pid=False):
        # pins_left = {'pwm': 12, 'dir': 24}
        self.motor_l = RMotor(pins_left['pwm'], pins_left['in1_pin'], pins_left['in2_pin'])
        self.motor_r = RMotor(pins_right['pwm'], pins_right['in1_pin'], pins_right['in2_pin'])
        self.odo = odo
        
        self.active_pid = active_pid
        # TODO
        # PID (ajustez Kp, Ki, Kd selon vos tests)
        self.pid_l = PIDController(1.0, 0.1, 0.05)
        self.pid_r = PIDController(1.0, 0.1, 0.05)
        
        self.target_v_l = 0.0
        self.target_v_r = 0.0
        
        self.wheel_base_width = wheel_base_width
        
        if not self.active_pid:
            logging.warning("[Robot Thread] Not active PID")

    @property        
    def target_linear(self):
        return (self.target_v_l + self.target_v_r )/2

    def move(self, linear, angular=0):
        """Set target velocity (m/s et rad/s)"""
        
        MAX_LINEAR =  90 #0.5  # 0.5 m/s
        linear = max(min(linear, MAX_LINEAR), -MAX_LINEAR)
        
        self.target_v_l = linear - angular #linear - (angular * self.wheel_base_width / 2)
        self.target_v_r = linear + angular #linear + (angular * self.wheel_base_width / 2)
        
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

    def update(self, dt):
        """
        Boucle de contrôle appelée par le RobotController
        """
        
        if not self.active_pid:
            # Apply the same velocity
            self.motor_l.set_speed(self.target_v_l)
            self.motor_r.set_speed(self.target_v_r)
            print("Set Motor speed")
            return
        
        # 1. Obtenir les vitesses réelles via odométrie
        _, dist_l = self.odo.left_wheel.get_delta_and_reset()
        _, dist_r = self.odo.right_wheel.get_delta_and_reset()
        
        v_real_l = dist_l / dt
        v_real_r = dist_r / dt
        
        # 2. Calculer le PWM via PID
        out_l = self.pid_l.compute(self.target_v_l, v_real_l)
        out_r = self.pid_r.compute(self.target_v_r, v_real_r)
        
        # 3. Appliquer aux moteurs
        self.motor_l.set_speed(out_l)
        self.motor_r.set_speed(out_r)
        
    def stop(self):
        self.motor_l.stop()
        self.motor_r.stop()
        
        if self.odo:
            self.odo.stop()
        
        logging.info("[Rover] Rover stopped")
        

class RoverThread(threading.Thread):
    def __init__(self, rover: Rover, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.rover = rover
        
        self.stop_event = threading.Event()
        self.daemon = True
        
        self.hz = 50 # Frequency of PID (20ms)
        
    def run(self):
        """Boucle haute fréquence du PID"""
        
        last_time = time.perf_counter()
        
        while not self.stop_event.is_set():
            now = time.perf_counter()
            dt = now - last_time
            #print("dt=", dt, "last_time", last_time, "Limit: ", 1.0 / self.hz)
            
            if dt >= (1.0 / self.hz):
                self.rover.update(dt)
                print("Call Update on rover")
                
                last_time = now
            
            # Make some pause
            time.sleep(0.001)
        
        logging.info("[RoverThread] Loop finished")
        
    def shutdown(self):
        self.stop_event.set()
        logging.info("[RoverThread] Has set stop Event")
        self.rover.stop()
        logging.info("[RoverThread] Rover stopped")
        
        