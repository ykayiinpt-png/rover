import time

import RPi.GPIO as GPIO

from src.core.utils import sign

class RMotor:
    def __init__(self, pwm_pin: int, in1_pin: int, in2_pin: int, frequency=100):
        self.pwm_pin = pwm_pin
        self.in1_pin = in1_pin
        self.in2_pin = in2_pin
        
        # Setup des pins
        GPIO.setup(self.pwm_pin, GPIO.OUT)
        GPIO.setup(self.in1_pin, GPIO.OUT)
        GPIO.setup(self.in2_pin, GPIO.OUT)
        
        # Initialisation du PWM
        self.pwm = GPIO.PWM(self.pwm_pin, frequency)
        self.pwm.start(0)
        
        self._dir = 0
        

    def set_speed(self, power):
        """
        power: valeur entre -100 et 100
        """
        
        #self.pwm.ChangeDutyCycle(40)
        print(f"Motor {self.pwm_pin} has changed duty cyle to: {power}")
        
        if self._dir != sign(power):
            self.pwm.ChangeDutyCycle(0)
            self._dir = sign(power)

        #return
        # Handle the direction
        # position turn forward, negative reverse
        if power >= 0: 
            GPIO.output(self.in1_pin, False)
            GPIO.output(self.in2_pin, True)
            duty_cycle = power
        else:
            # NOTE: Need the two motor to be running
            GPIO.output(self.in1_pin, True)
            GPIO.output(self.in2_pin, False)
            duty_cycle = -power # On repasse en positif pour le PWM
            
        # Limitation de sécurité
        duty_cycle = max(0, min(float(duty_cycle), 99))
        print(f"Setting duty cylce: {self.pwm_pin}", duty_cycle)
        self.pwm.ChangeDutyCycle(duty_cycle)

    def stop(self):
        self.pwm.ChangeDutyCycle(0)
