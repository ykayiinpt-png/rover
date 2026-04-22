import time
import threading
from typing import Any
import RPi.GPIO as GPIO

from collections import deque
import statistics

class UltrasoundSensorFilter:
    def __init__(self, window_size=5):
        self.history = deque(maxlen=window_size)

    def add_and_get(self, value):
        self.history.append(value)
        return statistics.median(self.history)


class UltrasoundSensor:
    """
    Object Wrapping for ultrasound sensor
    """
    
    def __init__(self, name, key: str, trig_pin: int, echo_pin: int):
        self.name = name
        self.key = key
        
        print(name, key, trig_pin, echo_pin)
        
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        
        self.start_time = 0
        self.end_time = 0
        self.distance = 0.0
        self.new_data_available = False

        # Setup GPIO
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)

        # Interruption : to detect the rising edge and the falling edge
        GPIO.add_event_detect(self.echo_pin, GPIO.BOTH, callback=self._echo_callback)

    def _echo_callback(self, channel):
        """Handler for echo response"""
        now = time.perf_counter()
        if GPIO.input(self.echo_pin):
            # We do have a rising edge, start sound emit
            self.start_time = now
        else:
            # We got a response back
            self.end_time = now
            self._calculate_distance()

    def _calculate_distance(self):
        duration = self.end_time - self.start_time
        # Distance = (temps * vitesse du son) / 2
        self.distance = (duration * 343) / 2  # en m
        self.new_data_available = True

    def trigger(self):
        """Send pulses and wait to compute the mesure"""
        self.new_data_available = False
        GPIO.output(self.trig_pin, True)
        time.sleep(0.00001)  # 10 microseconds (As defined in the documentation)
        GPIO.output(self.trig_pin, False)

    def get_distance(self):
        return round(self.distance, 2)
    
    def stop(self):
        """
        Deactivate resources and clear ressources
        """
        try:
            GPIO.remove_event_detect(self.echo_pin)
            
            GPIO.output(self.trig_pin, False)
            print(f"Capteur {self.name} arrêté proprement.")
        except Exception as e:
            print(f"Erreur lors de l'arrêt de {self.name}: {e}")
    
    
class UltrasoundSensorArray:
    def __init__(self, sensors_config: list[dict[str, Any]]):
        self.sensors = [
            UltrasoundSensor(cfg['name'], cfg['key'], cfg['trig'], cfg['echo']) 
            for cfg in sensors_config
        ]
        self.last_scan_data = {}

    def scan_sequence(self):
        """
        Execute a sequential reading of the sensors
        """
        for sensor in self.sensors:
            sensor.trigger()
            # We wait for the trigger to finish (max 30ms for ~5m)
            time.sleep(0.03) 
            self.last_scan_data[sensor.key] = sensor.get_distance()
            
        # TODO: to be removed
        print("Ultrasound (m)", self.last_scan_data)
        
        return self.last_scan_data
    
    def shutdown(self):
        """
        Stop all sensors
        """
        for sensor in self.sensors:
            sensor.stop()
