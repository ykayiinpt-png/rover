import faulthandler

from src.raspberry.exploration import ExplorationPlanner
from src.raspberry.log import PiLogger
from src.raspberry.video.process import CameraProcess
faulthandler.enable()


import logging
import threading

import numpy as np

from src.core.shared import MemorySharedDict
from src.raspberry.mapping.grid import OccupancyMap
from src.raspberry.mapping.kalman import KalmanMapping
from src.raspberry.mapping.process import MappingProcess
from src.raspberry.navigation import Navigation
from src.raspberry.config import Config
from src.raspberry.hardware.rover import Rover
from src.raspberry.hardware.rover.odometry import WheelOdometry

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
    rover_shared_state = MemorySharedDict(manager=processing_manager)
    mapping_shared_state = MemorySharedDict(manager=processing_manager)
    navigation_shared_state = MemorySharedDict(manager=processing_manager)
    
    rover_shared_state_command_lock = multiprocessing.Lock()
    
    map_data_send_queue = multiprocessing.Queue(maxsize=1000)
    mapping_position_data_sent_queue=multiprocessing.Queue(maxsize=1000)
    ultrasound_data_sent_queue = multiprocessing.Queue(maxsize=1000)
    imu_data_send_queue=multiprocessing.Queue(maxsize=1000)
    odometry_data_sent_queue = multiprocessing.Queue(maxsize=1000)
    commands_send_queue = multiprocessing.Queue(maxsize=1000)
    commands_receive_queue = multiprocessing.Queue(maxsize=1000)
    log_sent_queue = multiprocessing.Queue(maxsize=1000)
    
    communication_process: CommunicationProcess = None
    camera_process: CameraProcess = None
    rover_mapping_process: MappingProcess =None
    
    pi_logger = PiLogger("RaspberryPI", log_sent_queue)
    rover_logger = PiLogger("Rover", log_sent_queue)
    rover_thread_logger = PiLogger("RoverThread", log_sent_queue)
    mapping_logger = PiLogger("Mapping", log_sent_queue)
    
    features = cfg.features
    
    if "data" in features:
        communication_process = CommunicationProcess(
            host=cfg.mqtt.host, port=cfg.mqtt.port,
            rover_shared_state=rover_shared_state, rover_shared_state_command_lock=rover_shared_state_command_lock,
            
            log_sent_queue=log_sent_queue,
            
            ultrasound_data_sent_queue=ultrasound_data_sent_queue,
            imu_data_send_queue=imu_data_send_queue,
            odometry_data_sent_queue=odometry_data_sent_queue,
            commands_send_queue=commands_send_queue,
            commands_receive_queue=commands_receive_queue,
            map_data_send_queue=map_data_send_queue,
            mapping_position_data_sent_queue=mapping_position_data_sent_queue
        )
    
    if "video" in features:
        camera_process = CameraProcess(
            cam_cmd=cfg.video.command.camera,
            ffmpeg_cmd=cfg.video.command.ffmpeg
        )
    
    sonar_array=UltrasoundSensorArray(
        sensors_config=[
            {
                'name': cfg.ultra_sounds.front.name,  "key": cfg.ultra_sounds.front.key,
                'trig': cfg.ultra_sounds.front.gpio.trig, 'echo': cfg.ultra_sounds.front.gpio.echo,
                "angle_offset":  np.pi
            },
            {
                'name': cfg.ultra_sounds.back.name,  "key": cfg.ultra_sounds.back.key,
                'trig': cfg.ultra_sounds.back.gpio.trig, 'echo': cfg.ultra_sounds.back.gpio.echo,
                "angle_offset": 0
            },
            {
                'name': cfg.ultra_sounds.left.name,  "key": cfg.ultra_sounds.left.key,
                'trig': cfg.ultra_sounds.left.gpio.trig, 'echo': cfg.ultra_sounds.left.gpio.echo,
                "angle_offset": -np.pi/2
            },
            {
                'name': cfg.ultra_sounds.right.name,  "key": cfg.ultra_sounds.right.key,
                'trig': cfg.ultra_sounds.right.gpio.trig, 'echo': cfg.ultra_sounds.right.gpio.echo,
                "angle_offset": np.pi/2
            },
            #{'name': 'Front', "key": "u_f", 'trig': 20, 'echo': 21},
            #{'name': 'Right', "key": "u_r", 'trig': 26, 'echo': 7}, # NOTE: Have to disable SPI in order to add interruption to the pin 7 an SPI PIN
            #{'name': 'Left',  "key": "u_l", 'trig': 5, 'echo': 6}
        ],
        rover_shared_state=rover_shared_state,
        mapping_shared_state=mapping_shared_state,
        navigation_shared_state=navigation_shared_state,
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
        },
        rover_shared_state=rover_shared_state,
        mapping_shared_state=mapping_shared_state,
        navigation_shared_state=navigation_shared_state,
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
    
    # The nabigation
    rover_navigation = Navigation(
        shared_state=navigation_shared_state,
        map_data_sent_queue=map_data_send_queue,
        angle_threshold=cfg.navigation.angle_threshold,
        dist_threshold=cfg.navigation.dist_threshold,
        dim_l=cfg.navigation.dim.l, dim_w=cfg.navigation.dim.w
    )
    
    if cfg.navigation.waypoint.run:
        rover_navigation.set_waypoints(cfg.navigation.waypoint.items)
    
    # The explorer Planner
    rover_explorer = ExplorationPlanner(
        safe_avoid_angle=cfg.exploration.angle_threshold,
        safe_distance=cfg.exploration.dist_threshold,
        rover_shared_state=rover_shared_state,
        mapping_shared_state=mapping_shared_state,
        navigation_shared_state=navigation_shared_state,
    )
    
    # Mapping Process
    ekf = KalmanMapping(dt=None)
    occupancy_grid = OccupancyMap(
        width_m=cfg.mapping.occupancy_grid.width,
        height_m=cfg.mapping.occupancy_grid.width,
        resolution_x=cfg.mapping.occupancy_grid.resolution.x,
        resolution_y=cfg.mapping.occupancy_grid.resolution.y,
        save_grid_to_file=cfg.mapping.occupancy_grid.save_file_on_stop
    )
    rover_mapping_process =  MappingProcess(
        ekf=ekf, occupacy_grid=occupancy_grid,
        mapping_position_data_sent_queue=mapping_position_data_sent_queue,
        rover_shared_state=rover_shared_state,
        mapping_shared_state=mapping_shared_state,
        navigation_shared_state=navigation_shared_state,
    )
    
    rover = Rover(
        navigation=rover_navigation,
        explorer=rover_explorer,
        control_mode=Rover.MODE_MANUAL_NAVIGATION, #Rover.MODE_AUTONOMOUS_EXPLORATION, #Rover.MODE_WAYPOINTS_NAVIGATION, # Rover.MODE_MANUAL_NAVIGATION,
        base_velocity=cfg.rover.velocity,
        base_rotation_velocity=cfg.rover.velocity_rotate,
        swivel_velocity_pwm=cfg.rover.swivel_velocity_pwm,
        no_pid_stright_direction_pwm_dutycycle_value=cfg.rover.no_pid_stright_direction_pwm,
        shared_state=rover_shared_state,
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
        active_angle_pid=cfg.rover.enable_angle_pid,
        
        logger=rover_logger
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
        
        
        # Shared state
        rover_shared_state=rover_shared_state,
        mapping_shared_state=mapping_shared_state,
        navigation_shared_state=navigation_shared_state,
        
        logger=pi_logger,
        rover_thread_logger=rover_thread_logger
    )
    print(raspberry_pi_instance)
    

    try:
        if "data" in features:
            communication_process.start()
            logging.info("[Main] Communication process scheduled to start")
            
        if "video" in features:
            camera_process.start()
            logging.info("[Main] Camera process scheduled to start")
            
        if cfg.mapping.enabled:
            rover_mapping_process.start()
        
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
        mapping_position_data_sent_queue.close()
        ultrasound_data_sent_queue.close()
        imu_data_send_queue.close()
        odometry_data_sent_queue.close()
        commands_send_queue.close()
        commands_receive_queue.close()
        
        map_data_send_queue.join_thread()
        mapping_position_data_sent_queue.join_thread()
        ultrasound_data_sent_queue.join_thread()
        imu_data_send_queue.join_thread()
        odometry_data_sent_queue.join_thread()
        commands_send_queue.join_thread()
        commands_receive_queue.join_thread()
        
        logging.info("[RaspbarryPi] Queues closed")
        
        if "data" in features:
            try:
                # NOTE: Not to call. The function is asynchronnous
                # and is already handled insite the process
                # that runs an event loop
                # communication_process.stop()
                
                if communication_process is not None and communication_process.is_alive():
                    communication_process.terminate()
                    communication_process.join(timeout=5)

                    if communication_process.is_alive():
                        logging.warning("[Main] [communication_process] Server Force killing Communcation process...")
                        communication_process.kill()

                logging.info("[Main] [communication_process] Clean exit.")
            except Exception as e:
                logging.exception("[Main] communication_process Exception while running")
        
        if "video" in features:
            try:
                # Here we have to call stop
                camera_process.stop()
                time.sleep(5)
                
                if camera_process is not None and camera_process.is_alive():
                    camera_process.terminate()
                    camera_process.join(timeout=5)

                    if camera_process.is_alive():
                        logging.warning("[Main] [CameraProcess] Server Force killing Communcation process...")
                        camera_process.kill()

                logging.info("[Main] [CameraProcess] Clean exit.")
            except Exception as e:
                logging.exception("[Main] CameraProcess Exception while running")
                
        if cfg.mapping.enabled:
            try:
                if rover_mapping_process is not None and rover_mapping_process.is_alive():
                    rover_mapping_process.terminate()
                    rover_mapping_process.join(timeout=5)

                    if rover_mapping_process.is_alive():
                        logging.warning("[Main] Rover Mapping Server Force killing Communcation process...")
                        rover_mapping_process.kill()

                logging.info("[Main] [Rover Mapping] Clean exit.")
            except Exception as e:
                logging.exception("[Main] Rover Mapping Exception while running")
                
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
