import time

from src.core.utils import clamp, sign


class PIDController:
    def __init__(self, name, kp, ki, kd):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.prev_error = 0
        self.integral = 0
        self.prev_derivative = 0
        self.last_time = time.perf_counter()
        self.name = name
        self.out_filtered = 0
        self.out_smoothing_alpha = 0.9
        self.derivative_filtered = 0
        self.derivative_smoothing_alpha = 0.9999
        
    def interrupt(self):
        self.integral = 0
        self.prev_error = 0
        self.derivative_filtered = 0
        self.out_filtered = 0

    def compute(self, target_speed, current_speed):
        now = time.perf_counter()
        dt = now - self.last_time
        if dt <= 0: return 0
        
        error = target_speed - current_speed
        if abs(error) < 2: # Wind down the error
            error = 0
            
        if abs(error) >= 100:
            pass #error = 100 * sign(error)
            
        print(f"PID {self.name} target_speed diff: ", error, " Target", target_speed)
        self.integral += error * dt #+ Kaw * (output_sat - output)
        
        #self.integral = clamp(self.integral, -10, 10)
        derivative = (error - self.prev_error) / dt
        self.derivative_filtered = (
            self.derivative_smoothing_alpha * self.derivative_filtered +
            (1 - self.derivative_smoothing_alpha) * derivative
        )
        derivative = self.derivative_filtered
        print("Derivation: ", derivative)
        print("Integral: ", self.integral)
        
        print("\n\n\n")
        
        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)
        
        self.prev_error = error
        self.prev_derivative = derivative
        self.last_time = now
        
        #output_sat = clamp(output, -30, 30)
        
        #float u_sat = clamp(u, umin, umax);
        #I += Ki * erreur * dt + Kb * (u_sat - u);
        
        # On limite la sortie entre -100% et 100% de PWM
        
        self.out_filtered = (
            self.out_smoothing_alpha * self.out_filtered +
            (1 - self.out_smoothing_alpha) * output
        )
        
        return self.out_filtered
