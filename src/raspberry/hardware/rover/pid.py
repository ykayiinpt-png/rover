import time


class PIDController:
    def __init__(self, name, kp, ki, kd):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.prev_error = 0
        self.integral = 0
        self.last_time = time.perf_counter()
        self.name = name
        
    def interrupt(self):
        self.integral = 0
        self.prev_error = 0

    def compute(self, target_speed, current_speed):
        now = time.perf_counter()
        dt = now - self.last_time
        if dt <= 0: return 0
        
        error = target_speed - current_speed
        print(f"PID {self.name} target_speed diff: ", error, " Target", target_speed)
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt
        print("Derivation: ", derivative)
        print("Integral: ", self.integral)
        
        print("\n\n\n")
        
        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)
        
        self.prev_error = error
        self.last_time = now
        
        # On limite la sortie entre -100% et 100% de PWM
        return max(min(output, 100), -100)
