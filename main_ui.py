import argparse
import logging
import multiprocessing
import os
import sys

from src.ui.graphics.controls.process import RaspberryCommandsAckProcess
from src.ui.graphics.process import RaspberryDataExchangeProcess
from src.ui.log import LogWidget

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        print("Setting event policy...")
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    

from PyQt6.QtWidgets import QApplication

from src.ui import MainWindow
from src.ui.video.process import VstreamClientProcess


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

#logging.getLogger("aioice").setLevel(logging.DEBUG)
#logging.getLogger("aiortc").setLevel(logging.DEBUG)

def main(io_url: str, mqtt_host: str, mqtt_port: int, features: list[str]):
    video_frame_compute_result_queue = None
    map_data_queue = None
    sensors_ultrasound_data_queue = None
    sensors_imu_data_queue = None
    commands_send_queue = None
    commands_receive_queue = None
    
    video_stream_process = None
    raspberry_data_process = None
    commands_process = None
    
    
    
    window = None

    try:
        # Queus
        video_frame_compute_result_queue = multiprocessing.Queue(maxsize=1000)
        map_data_queue = multiprocessing.Queue(maxsize=1000)
        sensors_ultrasound_data_queue = multiprocessing.Queue(maxsize=1000)
        commands_send_queue = multiprocessing.Queue(maxsize=1000)
        commands_receive_queue = multiprocessing.Queue(maxsize=1000)
        
        
        app = QApplication(sys.argv)
                
        

        window = MainWindow(
            # Video streaming queue
            video_frame_compute_result_queue=video_frame_compute_result_queue,
            
            # Sensors data queues,
            map_data_queue=map_data_queue,
            sensors_ultrasound_data_queue=sensors_ultrasound_data_queue,
            sensors_imu_data_queue=None,
            
            # Commands
            commands_send_queue=commands_send_queue,
            commands_receive_queue=commands_receive_queue,            
        )
        
        # Start the video frame processing
        if "video" in features:
            video_stream_process =  VstreamClientProcess(
                compute_result_queue=video_frame_compute_result_queue,
                io_url=io_url
            ) 
            # RtcTrackClientProcess(compute_result_queue=result_queue)
        
        if "commands" in features:
            commands_process = RaspberryCommandsAckProcess(
                host=mqtt_host, port=mqtt_port,
                send_queue=commands_send_queue,
                receive_queue=commands_receive_queue
            )
            
        if "data" in features:
            raspberry_data_process = RaspberryDataExchangeProcess(
                host=mqtt_host, port=mqtt_port,
                map_data_queue=map_data_queue,
                sensors_ultrasound_data_queue=sensors_ultrasound_data_queue,
                sensors_imu_data_queue=sensors_imu_data_queue
            )
        
        if "video" in features:
            video_stream_process.start()
            
        if "data" in features:
            raspberry_data_process.start()
            
        if "commands" in features:
            commands_process.start()
        
        window.show()

        app.exec()
    except Exception:
        logging.exception("Exception while running main app")
        raise
    finally:
        print("In finally")
        print("Application Window", window)
        
        video_frame_compute_result_queue.close()
        video_frame_compute_result_queue.join_thread()
        
        map_data_queue.close()
        map_data_queue.join_thread()
        sensors_ultrasound_data_queue.close()
        sensors_ultrasound_data_queue.join_thread()
        
        commands_send_queue.close()
        commands_receive_queue.close()
        commands_receive_queue.join_thread()
        commands_send_queue.join_thread()
        
        # Stop the computing process
        if "video" in features:
            try:
                if video_stream_process is not None and video_stream_process.is_alive():
                    video_stream_process.terminate()
                    logging.info('[AppUI] teminate computing process')
                    video_stream_process.join(timeout=50)
                    logging.info('[AppUI] joined computing process')


                    if video_stream_process.is_alive():
                        logging.warning('[AppUI] killing computing process')
                        video_stream_process.kill()   
            except Exception as e:
                logging.exception("Exception occured while stopping")
            
        
        if "data" in features:
            try:
                if raspberry_data_process is not None and raspberry_data_process.is_alive():
                    raspberry_data_process.terminate()
                    logging.info('[AppUI] teminate raspberry data computing process')
                    raspberry_data_process.join(timeout=50)
                    logging.info('[AppUI] joined raspberry data computing process')


                    if raspberry_data_process.is_alive():
                        logging.warning('[AppUI] killing computing process')
                        raspberry_data_process.kill()   
            except Exception as e:
                logging.exception("Exception occured while stopping")
                
        if "commands" in features:
            try:
                if commands_process is not None and commands_process.is_alive():
                    commands_process.terminate()
                    logging.info('[AppUI] teminate raspberry data computing process')
                    commands_process.join(timeout=50)
                    logging.info('[AppUI] joined raspberry data computing process')


                    if commands_process.is_alive():
                        logging.warning('[AppUI] killing computing process')
                        commands_process.kill()   
            except Exception as e:
                logging.exception("Exception occured while stopping")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    parser.add_argument(
        "--ws_uri",
        type=str,
        default="http://127.0.0.1:8000",
        help="Host (e.g. http://127.0.0.1:8000)"
    )
    
    parser.add_argument(
        "--mqtt_host",
        type=str,
        default="127.0.0.1",
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
        choices=["video", "data", "commands"],
        required=True,
        help="Features to activate, video processing, data excahnge and remote commands"
    )
    
    args = parser.parse_args()
    try:
        main(
            io_url=args.ws_uri,
            mqtt_host=args.mqtt_host, mqtt_port=args.mqtt_port,
            features=args.feature)
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.exception("Exception occured...")
        raise e