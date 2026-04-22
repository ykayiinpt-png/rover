import logging

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
            [{'name': 'b', 'trig': 16, 'echo': 19}]
        )
        print("Sensors")
        
        robot_ctrl = RobotController(
            sonar_array=sonar_array,
            imu=IMUSensor(name="i"),
            
            # TODO: add this later
            odometry=None
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

