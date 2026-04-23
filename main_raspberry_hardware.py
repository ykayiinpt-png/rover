import logging

from src.raspberry.hardware.rover import Rover
from src.raspberry.imu_ekf_controller import ImuEkfController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


from RPi import GPIO

try:
    GPIO.cleanup()
except Exception:
    pass


GPIO.setmode(GPIO.BCM)

from src.raspberry.controller import RobotController
from src.raspberry.hardware.sensors.imu import IMUSensor
from src.raspberry.hardware.sensors.ultrasound import UltrasoundSensorArray


def main():
    robot_ctrl = None
    try:
        sonar_array=UltrasoundSensorArray(
            [
                {'name': 'Back',  "key": "u_b", 'trig': 16, 'echo': 19},
                {'name': 'Front', "key": "u_f", 'trig': 20, 'echo': 21},
                {'name': 'Right', "key": "u_r", 'trig': 26, 'echo': 7}, # NOTE: Have to disable SPI in order to add interruption to the pin 7 an SPI PIN
                {'name': 'Left',  "key": "u_l", 'trig': 5, 'echo': 6}
            ]
        )
        
        rover = Rover(
            odo= None,
            pins_left={"pwm": 12 , "in1_pin": 17 , "in2_pin": 27}, pins_right={"pwm": 13 , "in1_pin": 22 , "in2_pin": 23},
            wheel_base_width=0.10 # 10 cm -> 0.10 m
        )
        
        robot_ctrl = ImuEkfController(
            rover=rover,
            sonars_arr_obj=sonar_array,
            imu=IMUSensor(name="i")
        )
        print(robot_ctrl)
        
        robot_ctrl.run()
    except Exception as e:
        print("Has exception")
        raise e
    finally:
        if robot_ctrl is not None:
            robot_ctrl.stop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Exception occured")
        
    try:
        GPIO.cleanup()
    except Exception:
        pass

