import time

import RPi.GPIO as GPIO

from src.core.utils import sign

class RMotor:
    def __init__(self, pwm_pin: int, in1_pin: int, in2_pin: int, pwm=100, max_power: int=50):
        """
        :param max_power: the maximum power allow to be supplied to the
        motor
        """
        
        self.pwm_pin = pwm_pin
        self.in1_pin = in1_pin
        self.in2_pin = in2_pin
        
        self.max_power = max_power
        
        # Setup des pins
        GPIO.setup(self.pwm_pin, GPIO.OUT)
        GPIO.setup(self.in1_pin, GPIO.OUT)
        GPIO.setup(self.in2_pin, GPIO.OUT)
        
        # Initialisation du PWM
        self.pwm = GPIO.PWM(self.pwm_pin, pwm)
        self.pwm.start(0)
        

    def set_speed(self, power):
        """
        Set the motor dutycycle value
        
        :param power: the dutycycle value to send to the motor. In case it is
            a negative, the motor will move in the backward directtion. The value will be wrapped to the limits if it is less that the minimum set or greater 
            than the maximum set
        """

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
        duty_cycle = max(0, min(float(duty_cycle), self.max_power))
        self.pwm.ChangeDutyCycle(duty_cycle)

    def stop(self):
        self.pwm.ChangeDutyCycle(0)
