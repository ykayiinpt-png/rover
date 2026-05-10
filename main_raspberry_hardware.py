import logging
import faulthandler
import threading

from src.raspberry.navigation import Navigation
faulthandler.enable()

from src.raspberry.config import Config
from src.raspberry.hardware.rover import Rover
from src.raspberry.hardware.rover.odometry import WheelOdometry
from src.raspberry.mapping.imu_ekf_controller import ImuEkfController

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
    
    processing_manager = multiprocessing.Manager()
    rover_shared_state = processing_manager.dict()
    rover_shared_state_command_lock = multiprocessing.Lock()
    
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
            rover_shared_state=rover_shared_state, rover_shared_state_command_lock=rover_shared_state_command_lock,
            ultrasound_data_sent_queue=ultrasound_data_sent_queue,
            imu_data_send_queue=imu_data_send_queue,
            odometry_data_sent_queue=odometry_data_sent_queue,
            commands_send_queue=commands_send_queue,
            commands_receive_queue=commands_receive_queue,
            map_data_send_queue=map_data_send_queue,
        )
    
    sonar_array=UltrasoundSensorArray(
        [
            {
                'name': cfg.ultra_sounds.back.name,  "key": cfg.ultra_sounds.back.key,
                'trig': cfg.ultra_sounds.back.gpio.trig, 'echo': cfg.ultra_sounds.back.gpio.echo
            },
            {
                'name': cfg.ultra_sounds.front.name,  "key": cfg.ultra_sounds.front.key,
                'trig': cfg.ultra_sounds.front.gpio.trig, 'echo': cfg.ultra_sounds.front.gpio.echo
            },
            {
                'name': cfg.ultra_sounds.left.name,  "key": cfg.ultra_sounds.left.key,
                'trig': cfg.ultra_sounds.left.gpio.trig, 'echo': cfg.ultra_sounds.left.gpio.echo
            },
            {
                'name': cfg.ultra_sounds.right.name,  "key": cfg.ultra_sounds.right.key,
                'trig': cfg.ultra_sounds.right.gpio.trig, 'echo': cfg.ultra_sounds.right.gpio.echo
            },
            #{'name': 'Front', "key": "u_f", 'trig': 20, 'echo': 21},
            #{'name': 'Right', "key": "u_r", 'trig': 26, 'echo': 7}, # NOTE: Have to disable SPI in order to add interruption to the pin 7 an SPI PIN
            #{'name': 'Left',  "key": "u_l", 'trig': 5, 'echo': 6}
        ]
    )
    
    odometry = WheelOdometry(
        left_params={
            "name": cfg.rover.odometry.left_wheel.name,
            "pin": cfg.rover.odometry.left_wheel.gpio.pin, 
            "ticks_per_rev": cfg.rover.odometry.left_wheel.ticks_per_rev,
            "wheel_diameter":cfg.rover.odometry.left_wheel.wheel_diameter,
            "min_ticks_delta": cfg.rover.odometry.left_wheel.min_ticks_delta,
            "lpf_1_alpha": cfg.rover.odometry.left_wheel.lpf_1_alpha,
            "window_filter_size": cfg.rover.odometry.left_wheel.window_filter_size
        },
        right_params={
            "name": cfg.rover.odometry.right_wheel.name,
            "pin": cfg.rover.odometry.right_wheel.gpio.pin, 
            "ticks_per_rev": cfg.rover.odometry.right_wheel.ticks_per_rev,
            "wheel_diameter":cfg.rover.odometry.right_wheel.wheel_diameter,
            "min_ticks_delta": cfg.rover.odometry.right_wheel.min_ticks_delta,
            "lpf_1_alpha": cfg.rover.odometry.right_wheel.lpf_1_alpha,
            "window_filter_size": cfg.rover.odometry.right_wheel.window_filter_size
        }
    )
    
    imu_sensor = IMUSensor(
        name="IMU_Sensor",
        bus_number=cfg.imu.bus_number,
        address=cfg.imu.bus_address,
        lpf_1_alpha=cfg.imu.gyro.z.lpf_1_alpha
    )
    imu_sensor_thread_lock = threading.Lock()
    
    # Calibrate the IMU
    imu_sensor.calibrate()
    
    rover_navigation = Navigation(
        map_data_sent_queue=map_data_send_queue,
        angle_threshold=cfg.navigation.angle_threshold,
        dist_threshold=cfg.navigation.dist_threshold,
        dim_l=cfg.navigation.dim.l, dim_w=cfg.navigation.dim.w
    )
    rover_navigation.set_waypoints(cfg.navigation.waypoints)
    
    rover = Rover(
        navigation=rover_navigation,
        control_mode= Rover.MODE_MANUAL_NAVIGATION, #Rover.MODE_WAYPOINTS_NAVIGATION, # Rover.MODE_MANUAL_NAVIGATION,
        base_velocity=cfg.rover.velocity,
        base_rotation_velocity=cfg.rover.velocity_rotate,
        shared_state=rover_shared_state,
        shared_state_command_lock=rover_shared_state_command_lock,
        odo= odometry,
        
        imu=imu_sensor,
        imu_sensor_thread_lock=imu_sensor_thread_lock,
        
        motor_right={
            "pwm_pin": cfg.rover.motor_right.gpio.pwm ,
            "in1_pin": cfg.rover.motor_right.gpio.in1,
            "in2_pin": cfg.rover.motor_right.gpio.in2,
            "max_power":  cfg.rover.motor_right.max_power,
            "pwm":  cfg.rover.motor_right.pwm
        },
        motor_left={
            "pwm_pin": cfg.rover.motor_left.gpio.pwm ,
            "in1_pin": cfg.rover.motor_left.gpio.in1,
            "in2_pin": cfg.rover.motor_left.gpio.in2,
            "max_power":  cfg.rover.motor_left.max_power,
            "pwm":  cfg.rover.motor_left.pwm
        },
        
        pid_motor_speed_right={
            "P": cfg.rover.motor_right.pid.kp,
            "I": cfg.rover.motor_right.pid.ki,
            "D": cfg.rover.motor_right.pid.kd,
            "max_integral": cfg.rover.motor_right.pid.max_integral
        },
        pid_motor_speed_left={
            "P": cfg.rover.motor_left.pid.kp,
            "I": cfg.rover.motor_left.pid.ki,
            "D": cfg.rover.motor_left.pid.kd,
            "max_integral": cfg.rover.motor_left.pid.max_integral
        },
        pid_angle={
            "P": cfg.rover.angle.straight.pid.kp,
            "I": cfg.rover.angle.straight.pid.ki,
            "D": cfg.rover.angle.straight.pid.kd
        },
        
        theta_target=cfg.rover.angle.straight.ref,
        pwm_bais_left=cfg.rover.motor_left.duty_cycle.bais,
        pwm_bais_right=cfg.rover.motor_right.duty_cycle.bais,
        
        wheels_base_distance=cfg.rover.odometry.wheels_base_distance,
        active_pid=cfg.rover.enable_pid,
        active_angle_pid=cfg.rover.enable_angle_pid
    )
    
    
    raspberry_pi_instance = RaspberryPi(
        rover=rover,
        sonars_arr_obj=sonar_array,
        imu=imu_sensor,
        imu_sensor_thread_lock=imu_sensor_thread_lock,
        ultrasound_data_sent_queue=ultrasound_data_sent_queue,
        imu_data_send_queue=imu_data_send_queue,
        odometry_data_sent_queue=odometry_data_sent_queue,
        commands_send_queue=commands_send_queue,
        commands_receive_queue=commands_receive_queue,
        map_data_send_queue=map_data_send_queue,
    )
    print(raspberry_pi_instance)
    

    try:
        if "data" in features:
            communication_process.start()
            logging.info("[Main] Communication process scheduled to start")
        
        logging.info("[Main] Main process running. Press Ctrl+C to stop.")

        raspberry_pi_instance.run()
    except KeyboardInterrupt:
        logging.info("[Main] KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        logging.exception("Exception occured While starting raspberry PI4")
        raise e
    finally:
        logging.info("[Main] In finally")
        
        # Stop the rapberry PI
        raspberry_pi_instance.stop()
        
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
