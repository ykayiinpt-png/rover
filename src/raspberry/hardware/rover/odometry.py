import RPi.GPIO as GPIO
import time

class WheelEncoder:
    """
    Encoder used to measure the real velocity of wheel
    """
    
    def __init__(self, name, pin, ticks_per_rev, wheel_diameter_mm):
        self.name = name
        self.pin = pin
        self.ticks_per_rev = ticks_per_rev
        self.mm_per_tick = (wheel_diameter_mm * 3.14159) / ticks_per_rev
        
        self.total_ticks = 0
        self.last_delta_ticks = 0
        
        # Set up GPIO
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Interrupt
        GPIO.add_event_detect(self.pin, GPIO.RISING, callback=self._tick_callback)

    def _tick_callback(self, channel):
        """
        Handler to increment the tick
        """
        self.total_ticks += 1

    def get_delta_and_reset(self):
        """
        Returns the accumulated ticks since the last call
        
        Will be used by filters for position estimation
        """
        current_ticks = self.total_ticks
        delta = current_ticks - self.last_delta_ticks
        self.last_delta_ticks = current_ticks
        
        distance_mm = delta * self.mm_per_tick
        return delta, distance_mm

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
        l_ticks, l_dist = self.left_wheel.get_delta_and_reset()
        r_ticks, r_dist = self.right_wheel.get_delta_and_reset()
        
        # Average distance traveled by the robot
        avg_distance = (l_dist + r_dist) / 2.0
        
        return {
            "distance": avg_distance, # mm
            "left_dist": l_dist,
            "right_dist": r_dist
        }

    def stop(self):
        self.left_wheel.stop()
        self.right_wheel.stop()