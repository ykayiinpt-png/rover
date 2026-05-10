import RPi.GPIO as GPIO
import time

import numpy as np

from src.core.filter import LowPassFilter1Order

class SlidingWindow:
    def __init__(self, size):
        self.size = size
        self.data = [0] * size
        self.index = 0
        self.cumul = 0

    def filter(self, valeur_brute):
        # Soustrait la valeur sortante et ajoute la entrante
        self.cumul -= self.data[self.index]
        self.data[self.index] = valeur_brute
        self.cumul += valeur_brute
        
        # Avance l'index circulairement
        self.index = (self.index + 1) % self.size
        
        return self.cumul / self.size
    
    def reset(self):
        self.data = [0] * self.size
        self.index = 0
        self.cumul = 0
        

# class WheelEncoder:
#     """
#     Mesure the velocity of the wheel
#     """
    
#     def __init__(self, name, pin, ticks_per_rev, wheel_diameter, timeout=0.2, velocity_smoothing_alpha=0.99):
#         """
#         :param name: a name to the current encoder
#         :param ticks_per_rev: Number of ticks per revolution, by default we do have 20
#         """
        
#         self.name = name
#         self.pin = pin
        
#         """
#         Tick per revolution
#         """
#         self.ticks_per_rev = ticks_per_rev
        
#         """
#         The current velocity
#         """
#         self.current_rpm = 0.0
        
#         """
#         After the time out we consider, the velocity to be zero
#         """
#         self.timeout = 0.2 
        
#         self.distance_per_tick = (wheel_diameter * np.pi) / ticks_per_rev
        
#         self.filter = SlidingWindow(size=1)
        
        
#         self.velocity_filtered = 0 # Will be ued to smooth the velocity and avoid spikes
        
#         # Set up GPIO
#         GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
#         # Interrupt
#         GPIO.add_event_detect(self.pin, GPIO.RISING, callback=self._tick_callback)
        
#         self.last_tick_time = time.perf_counter()

#     def _tick_callback(self, channel):
#         """
#         Call at the rising event occurance at the wheel encoder pin
#         """
#         now = time.perf_counter()
#         dt = now - self.last_tick_time
        
#         if dt > 0.002: # Debouncing
#             # Formula : 1 tick / dt = ticks per seconde
#             # (ticks_per_sec / ticks_per_rev) * 60 = RPM
#             self.current_rpm = (1.0 / dt / self.ticks_per_rev) * 60.0
#             self.last_tick_time = now
            
#     def get_delta_and_reset(self):
#         """
#         Returns the current velocitY with stopsafety guard
#         """
#         if (time.perf_counter() - self.last_tick_time) > self.timeout:
#             self.current_rpm = 0.0
            
#         # Just to be conform to the previous tick counter encoder
        
#         return self.current_rpm
    
#     def reset(self):
#         """
#         Reset Chieck counter. Called specially if 
#         velocity is set to 0
#         """
#         self.filter.reset()
    
#     def stop(self):
#         GPIO.remove_event_detect(self.pin)
#         print(f"Encodeur {self.name} arrêté.")
    


class WheelEncoder:
    """
    Encoder used to measure the real velocity of wheel
    """
    
    def __init__(self, name, pin, 
                ticks_per_rev, wheel_diameter,
                min_ticks_delta=2,
                lpf_1_alpha=0.8,
                window_filter_size=2):
        """
        :param lpf_1_alpha: the alpha coefficient fo the first order filter
        applied to the computed velocity 
        """
        
        self.name = name
        self.pin = pin
        """
        Tick per revolution
        """
        self.ticks_per_rev = ticks_per_rev
        self.distance_per_tick = float((wheel_diameter * np.pi) / ticks_per_rev)
        self.wheel_diameter = wheel_diameter
        
        #self.filter = SlidingWindow(size=window_filter_size)
        self.filter =  LowPassFilter1Order(alpha=lpf_1_alpha) 
        
        self.min_ticks_delta = min_ticks_delta
        self.total_ticks = 0
        self.last_delta_ticks = 0
        self.last_time = time.perf_counter()
        self.velocity_filtered = 0
        
        ########################
        # GPIO
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Interrupt
        GPIO.add_event_detect(self.pin, GPIO.RISING, callback=self._tick_callback)

    def _tick_callback(self, channel):
        """
        Handler to increment the tick
        """
        self.total_ticks += 1
        
    def reset(self):
        """
        Reset Chieck counter. Called specially if 
        velocity is set to 0
        """
        
        self.total_ticks = 0
        self.last_delta_ticks = 0
        self.filter.reset()
        self.velocity_filtered = 0

    def get_delta_and_reset(self):
        """
        Returns the accumulated ticks, the distance, and the velocity
        since the last call
        
        Will be used by filters for position estimation
        """
        now = time.perf_counter()
        dt = now - self.last_time
        
        current_ticks = self.total_ticks
        delta = current_ticks - self.last_delta_ticks
        if abs(delta) < self.min_ticks_delta:
            delta = 0
        
        dist = delta * self.distance_per_tick # TODO: THink is this correct ?
        self.last_delta_ticks = current_ticks
        
        # Compute the wheel speed
        if dt > 0:
            raw_velocity = (
                # Compute the revolution
                (delta / self.ticks_per_rev)
                / dt
            ) * 60 # Multiply by 60 convert RPsecond to RevolutionPer Minute
        else:
            raw_velocity = 0
        
        
        if raw_velocity < 400: # TODO: use a multiplier of the base velocity
            self.velocity_filtered = self.filter.filter(raw_velocity)
        #else:
        #    pass
        
        # Backup time
        self.last_time = now
        
        #print("V_Filtered: ", self.velocity_filtered)
        
        return delta, dist, self.velocity_filtered


    def stop(self):
        GPIO.remove_event_detect(self.pin)
        print(f"Encodeur {self.name} arrêté.")


class WheelOdometry:
    def __init__(self, left_params, right_params):
        self.left_wheel = WheelEncoder(
            name=left_params["name"], pin=left_params["pin"], 
            ticks_per_rev=left_params["ticks_per_rev"], wheel_diameter=left_params["wheel_diameter"],
            min_ticks_delta=left_params["min_ticks_delta"],
            lpf_1_alpha=left_params["lpf_1_alpha"],
            window_filter_size=left_params["window_filter_size"]
        )
        self.right_wheel = WheelEncoder(
            name=right_params["name"], pin=right_params["pin"], 
            ticks_per_rev=right_params["ticks_per_rev"], wheel_diameter=right_params["wheel_diameter"],
            min_ticks_delta=right_params["min_ticks_delta"],
            lpf_1_alpha=right_params["lpf_1_alpha"],
            window_filter_size=right_params["window_filter_size"]
        )

    def get_movement(self):
        """
        Compute the robot's average movement based on wheel motion.

        Returns:
            dict: Dictionary containing:
                - "avg_dist" (float): Average distance traveled by the robot.
                - "left" (dict): Movement data for the left wheel:
                    - "dist" (float): Distance traveled by the wheel.
                    - "v" (float): Wheel velocity.
                - "right" (dict): Movement data for the right wheel:
                    - "dist" (float): Distance traveled by the wheel.
                    - "v" (float): Wheel velocity.
        """
        #l_ticks, l_dist, l_v = self.left_wheel.get_delta_and_reset()
        #r_ticks, r_dist, r_v = self.right_wheel.get_delta_and_reset()
        
        l_ticks, l_dist = 0, 0
        r_ticks, r_dist = 0, 0
        
        #l_v = self.left_wheel.get_delta_and_reset()
        #r_v = self.right_wheel.get_delta_and_reset()
        
        l_ticks, l_dist, l_v = self.left_wheel.get_delta_and_reset()
        r_ticks, r_dist, r_v = self.right_wheel.get_delta_and_reset()
        
        # Average distance traveled by the robot
        avg_distance = (l_dist + r_dist) / 2.0
        
        return {
            "avg_dist": avg_distance, # mm
            "left": { "dist": l_dist, "v": l_v},
            "right": { "dist": r_dist, "v": r_v},
        }

    def stop(self):
        self.left_wheel.stop()
        self.right_wheel.stop()