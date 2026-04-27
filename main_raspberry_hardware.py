import logging
import faulthandler
faulthandler.enable()

from src.raspberry.config import Config
from src.raspberry.hardware.rover import Rover
from src.raspberry.hardware.rover.odometry import WheelOdometry
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

def main():
    cfg = Config()
    
    map_data_send_queue = multiprocessing.Queue(maxsize=1000)
    ultrasound_data_sent_queue = multiprocessing.Queue(maxsize=1000)
    imu_data_send_queue=multiprocessing.Queue(maxsize=1000)
    odometry_data_sent_queue = multiprocessing.Queue(maxsize=1000)
    commands_send_queue = multiprocessing.Queue(maxsize=1000)
    commands_receive_queue = multiprocessing.Queue(maxsize=1000)
    
    communication_process= None
    
    features = cfg.features
    
    if "data" in features:
        communication_process = CommunicationProcess(
            host=cfg.mqtt.host, port=cfg.mqtt.port,
            ultrasound_data_sent_queue=ultrasound_data_sent_queue,
            imu_data_send_queue=imu_data_send_queue,
            odometry_data_sent_queue=odometry_data_sent_queue,
            commands_send_queue=commands_send_queue,
            commands_receive_queue=commands_receive_queue,
            map_data_send_queue=map_data_send_queue,
        )
    
    sonar_array=UltrasoundSensorArray(
        [
            {'name': 'Back',  "key": "u_b", 'trig': 16, 'echo': 19},
            {'name': 'Front', "key": "u_f", 'trig': 20, 'echo': 21},
            {'name': 'Right', "key": "u_r", 'trig': 26, 'echo': 7}, # NOTE: Have to disable SPI in order to add interruption to the pin 7 an SPI PIN
            {'name': 'Left',  "key": "u_l", 'trig': 5, 'echo': 6}
        ]
    )
    
    odometry = WheelOdometry(
        left_pin=10, right_pin=9,
        tpr=20, diameter=0.065 # 6.5cm
    )
    
    rover = Rover(
        odo= odometry,
        pins_right={
            "pwm": cfg.rover.motor.gpio.right.pwm ,
            "in1_pin": cfg.rover.motor.gpio.right.in1,
            "in2_pin": cfg.rover.motor.gpio.right.in2
        },
        pins_left={
            "pwm": cfg.rover.motor.gpio.left.pwm ,
            "in1_pin": cfg.rover.motor.gpio.left.in1,
            "in2_pin": cfg.rover.motor.gpio.left.in2
        },
        pid_right={
            "P": cfg.rover.motor.pid.right.kp,
            "I": cfg.rover.motor.pid.right.ki,
            "D": cfg.rover.motor.pid.right.kd
        },
        pid_left={
            "P": cfg.rover.motor.pid.left.kp,
            "I": cfg.rover.motor.pid.left.ki,
            "D": cfg.rover.motor.pid.left.kd
        },
        pwm_bais_left=cfg.rover.motor.pwm.bais.left,
        pwm_bais_right=cfg.rover.motor.pwm.bais.right,
        
        wheel_base_width=cfg.rover.odometry.wheel_base_width,
        active_pid=cfg.rover.enable_pid
    )
    
    robot_ctrl = ImuEkfController(
        rover=rover,
        sonars_arr_obj=sonar_array,
        imu=IMUSensor(name="i"),
        
        ultrasound_data_sent_queue=ultrasound_data_sent_queue,
        imu_data_send_queue=imu_data_send_queue,
        odometry_data_sent_queue=odometry_data_sent_queue,
        commands_send_queue=commands_send_queue,
        commands_receive_queue=commands_receive_queue,
        map_data_send_queue=map_data_send_queue,
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
        
        map_data_send_queue.close()
        ultrasound_data_sent_queue.close()
        imu_data_send_queue.close()
        odometry_data_sent_queue.close()
        commands_send_queue.close()
        commands_receive_queue.close()
        
        map_data_send_queue.join_thread()
        ultrasound_data_sent_queue.join_thread()
        imu_data_send_queue.join_thread()
        odometry_data_sent_queue.join_thread()
        commands_send_queue.join_thread()
        commands_receive_queue.join_thread()
        
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
                
        try:
            GPIO.cleanup()
        except Exception:
            pass
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    parser.add_argument(
        "--conf_path",
        type=str,
        default="config.local.yml",
        help="Path to the config file a config.yml file"
    )
    
    args = parser.parse_args()
    
    
    try:
        cfg = Config(config_path=args.conf_path)
        
        main()
    except Exception as e:
        logging.exception("Exception in main")
    finally:
        try:
            GPIO.cleanup()
        except Exception:
            pass
