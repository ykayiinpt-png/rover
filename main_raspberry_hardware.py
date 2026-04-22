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





import argparse
import logging
import os
import sys
import time
import multiprocessing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        print("Setting event policy...")
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    

from src.raspberry.communication.process import CommunicationProcess
from src.raspberry.pi import RaspberryPi

def main(host: str, port: int, features: list[str]):
    raspberry_send_queue = multiprocessing.Queue(maxsize=1000)
    raspberry_receive_queue = multiprocessing.Queue(maxsize=1000)
    
    communication_process= None
    
    
    if "data" in features:
        communication_process = CommunicationProcess(
            host=host, port=port,
            send_queue=raspberry_send_queue, receive_queue=raspberry_receive_queue
        )
    
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
        pins_left={"pwm": 12 , "in1_pin": 17 , "in2_pin": 27},
        pins_right={"pwm": 13 , "in1_pin": 22 , "in2_pin": 23},
        wheel_base_width=0.10 # 10 cm -> 0.10 m
    )
    
    robot_ctrl = ImuEkfController(
        rover=rover,
        sonars_arr_obj=sonar_array,
        imu=IMUSensor(name="i"),
        
        ultrasound_send_queue=raspberry_send_queue#, receive_queue=raspberry_receive_queue
    )
    print(robot_ctrl)
    

    try:
        if "data" in features:
            communication_process.start()
            logging.info("[Main] Communication process scheduled to start")
        
        logging.info("[Main] Main process running. Press Ctrl+C to stop.")

        robot_ctrl.run()
    except KeyboardInterrupt:
        logging.info("[Main] KeyboardInterrupt received. Shutting down...")
        robot_ctrl.stop()
    except Exception as e:
        logging.exception("Exception occured While starting raspberry PI4")
        raise e
    finally:
        logging.info("[RaspbarryPi] In finally")
        
        raspberry_send_queue.close()
        raspberry_receive_queue.close()
        
        raspberry_send_queue.join_thread()
        raspberry_receive_queue.join_thread()
        
        logging.info("[RaspbarryPi] Queues closed")
        
        if "data" in features:
            try:
                if communication_process is not None and communication_process.is_alive():
                    communication_process.terminate()
                    communication_process.join(timeout=5)


                    if communication_process.is_alive():
                        logging.warning("[Main] Server Force killing Communcation process...")
                        communication_process.kill()

                logging.info("[Main] Clean exit.")
            except Exception as e:
                logging.exception("Exception while running")
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mqtt_host",
        type=str,
        required=True,
        help="MQTT Host (e.g. 127.0.0.1)"
    )

    parser.add_argument(
        "--mqtt_port",
        type=int,
        default=1883,
        help="MQTT Port number (default: 1883)"
    )
    
    parser.add_argument(
        "--feature",
        type=str,
        action='append',
        choices=["video", "data", "commands", "none"],
        required=True,
        help="Features to activate, video processing, data excahnge and remote commands"
    )
    
    args = parser.parse_args()
    
    
    try: 
        main(host=args.mqtt_host, port=args.mqtt_port, features=args.feature)
    except Exception as e:
        raise e

"""

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

"""