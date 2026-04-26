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
        
#         self.per_tick = (wheel_diameter * np.pi) / ticks_per_rev
        
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
    
    def __init__(self, name, pin, ticks_per_rev, wheel_diameter, velocity_smoothing_alpha=0.99):
        self.name = name
        self.pin = pin
        """
        Tick per revolution
        """
        self.ticks_per_rev = ticks_per_rev
        self.per_tick = (wheel_diameter * 3.14159) / ticks_per_rev
        self.wheel_diameter = wheel_diameter
        
        #self.filter = SlidingWindow(size=1000)
        self.filter =  SlidingWindow(size=5) # LowPassFilter1Order(alpha=0.9) # SlidingWindow(size=4) #(alpha=velocity_smoothing_alpha)
        
        self.total_ticks = 0
        self.last_delta_ticks = 0
        self.last_time = time.perf_counter()
        self.velocity_filtered = 0.8 # Will be ued to smooth the velocity and avoid spikes
        # Set up GPIO
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

    def get_delta_and_reset_old(self):
        """
        Returns the accumulated ticks since the last call. We found
        also the velocity and the distance
        
        Will be used by filters for position estimation
        
        @deprecated
        """
        now = time.perf_counter()
        dt = now - self.last_time
        
        current_ticks = self.total_ticks
        delta = current_ticks - self.last_delta_ticks
        if abs(delta) < 2:
            delta = 0
        
        self.last_delta_ticks = current_ticks
        #print(f"{self.name} Delta: ", delta, self.total_ticks)
        distance = delta * self.per_tick
        if dt > 0:
            raw_velocity = distance / dt
        else:
            raw_velocity = 0
        
        if raw_velocity != 0:
            self.velocity_filtered = self.filter.filter(raw_velocity)
        else:
            self.velocity_filtered = 0
            distance = 0
            
        self.last_time = now
    
        return delta, distance,  self.velocity_filtered
    
    def get_delta_and_reset(self):
        """
        Returns the accumulated ticks since the last call. We found
        also the velocity and the distance
        
        Will be used by filters for position estimation
        """
        now = time.perf_counter()
        dt = now - self.last_time
        
        current_ticks = self.total_ticks
        delta = current_ticks - self.last_delta_ticks
        if abs(delta) < 2:
            delta = 0
        
        self.last_delta_ticks = current_ticks
        #print(f"{self.name} Delta: ", delta, self.total_ticks)
        if dt > 0:
            revolutions  = delta / self.ticks_per_rev
            # Convert to RPM
            raw_velocity = (revolutions / dt) * 60
        else:
            raw_velocity = 0
        
        
        self.velocity_filtered = self.filter.filter(raw_velocity)
        
        self.last_time = now

        dist = 2*np.pi * self.wheel_diameter * self.velocity_filtered * dt
        return delta, dist, self.velocity_filtered


    def stop(self):
        GPIO.remove_event_detect(self.pin)
        print(f"Encodeur {self.name} arrêté.")


class WheelOdometry:
    def __init__(self, left_pin, right_pin, tpr, diameter):
        self.left_wheel = WheelEncoder("Gauche", left_pin, tpr, diameter)
        self.right_wheel = WheelEncoder("Droite", right_pin, tpr, diameter)

    def get_movement(self):
        """
        Compute the average movement of the robot
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
            "distance": avg_distance, # mm
            "left": { "dist": l_dist, "v": l_v},
            "right": { "dist": r_dist, "v": r_v},
        }

    def stop(self):
        self.left_wheel.stop()
        self.right_wheel.stop()