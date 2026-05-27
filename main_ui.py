import argparse
import logging
import multiprocessing
import os
import sys

from src.core.shared import MemorySharedDict
from src.raspberry.config import Config
from src.ui.heartbeat import Pi4HeartBeatAckProcess

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        print("Setting event policy...")
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())


from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


from src.ui.graphics.controls.process import RaspberryCommandsAckProcess
from src.ui.graphics.process import RaspberryDataExchangeProcess
from src.ui.log import LogWidget
from src.ui import MainWindow
from src.ui.video.process import VstreamClientProcess


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

#logging.getLogger("aioice").setLevel(logging.DEBUG)
#logging.getLogger("aiortc").setLevel(logging.DEBUG)

def main():
    cfg = Config()

    video_frame_compute_result_queue = None
    map_receive_data_queue = None
    mapping_state_receive_data_queue = None
    mapping_grid_data_receive_queue = None
    sensors_ultrasound_data_queue = None
    sensors_imu_data_queue = None
    odometry_data_queue = None
    commands_send_queue = None
    commands_receive_queue = None

    video_stream_process = None
    raspberry_data_process = None
    commands_process = None
    heatbeat_process = None

    log_received_queue=None



    window = None

    try:
        # Queus
        video_frame_compute_result_queue = multiprocessing.Queue(maxsize=1000)
        mapping_grid_data_receive_queue = multiprocessing.Queue(maxsize=2000)
        map_receive_data_queue = multiprocessing.Queue(maxsize=1000)
        mapping_state_receive_data_queue = multiprocessing.Queue(maxsize=1000)
        sensors_ultrasound_data_queue = multiprocessing.Queue(maxsize=1000)
        sensors_imu_data_queue=multiprocessing.Queue(maxsize=1000)
        odometry_data_queue = multiprocessing.Queue(maxsize=1000)
        commands_send_queue = multiprocessing.Queue(maxsize=1000)
        commands_receive_queue = multiprocessing.Queue(maxsize=1000)

        log_received_queue = multiprocessing.Queue(maxsize=1000)

        # Independant process
        processing_manager = multiprocessing.Manager()
        ui_state = MemorySharedDict(manager=processing_manager)

        # Init
        ui_state["alive"] = False
        ui_state["ia_objects"] = {}
        ui_state["ia_objects_available"] = False

        # Processes
        heatbeat_process = Pi4HeartBeatAckProcess(ui_state=ui_state, host=cfg.mqtt.host, port=cfg.mqtt.port)


        app = QApplication(sys.argv)
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)



        window = MainWindow(
            ui_state=ui_state,

            # Video streaming queue
            video_frame_compute_result_queue=video_frame_compute_result_queue,

            # Map data queues,
            map_receive_data_queue=map_receive_data_queue,
            mapping_state_receive_data_queue=mapping_state_receive_data_queue,
            mapping_grid_data_queue=mapping_grid_data_receive_queue,

            # Sensor data queues
            sensors_ultrasound_data_queue=sensors_ultrasound_data_queue,
            sensors_imu_data_queue=sensors_imu_data_queue,
            odometry_data_queue=odometry_data_queue,

            # Commands
            command_sent_data_queue=commands_send_queue,
            command_receive_data_queue=commands_receive_queue,

            # Video
            video_stream_enabled=cfg.video.enabled,
            video_stream_url=cfg.video.stream.url,

            log_received_queue=log_received_queue
        )

        # Start the video frame processing
        # if "video" in cfg.features:
        #     video_stream_process =  VstreamClientProcess(
        #         compute_result_queue=video_frame_compute_result_queue,
        #         io_url=io_url
        #     )
            # RtcTrackClientProcess(compute_result_queue=result_queue)

        if "commands" in cfg.features:
            commands_process = RaspberryCommandsAckProcess(
                host=cfg.mqtt.host, port=cfg.mqtt.port,
                send_queue=commands_send_queue,
                receive_queue=commands_receive_queue
            )

        if "data" in cfg.features:
            raspberry_data_process = RaspberryDataExchangeProcess(
                host=cfg.mqtt.host, port=cfg.mqtt.port,
                map_receive_data_queue=map_receive_data_queue,
                mapping_state_receive_data_queue=mapping_state_receive_data_queue,
                mapping_grid_data_queue=mapping_grid_data_receive_queue,
                sensors_ultrasound_data_queue=sensors_ultrasound_data_queue,
                sensors_imu_data_queue=sensors_imu_data_queue,
                odometry_data_queue=odometry_data_queue,
                log_received_queue=log_received_queue
            )

        # if "video" in features:
        #    video_stream_process.start()

        if "data" in cfg.features:
            raspberry_data_process.start()

        if "commands" in cfg.features:
            commands_process.start()

        heatbeat_process.start()

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

        map_receive_data_queue.close()
        mapping_state_receive_data_queue.close()
        mapping_grid_data_receive_queue.close()

        sensors_ultrasound_data_queue.close()
        sensors_imu_data_queue.close()
        odometry_data_queue.close()

        sensors_ultrasound_data_queue.join_thread()
        sensors_imu_data_queue.join_thread()
        odometry_data_queue.join_thread()

        map_receive_data_queue.join_thread()
        mapping_state_receive_data_queue.join_thread()
        mapping_grid_data_receive_queue.join_thread()


        commands_send_queue.close()
        commands_receive_queue.close()
        commands_receive_queue.join_thread()
        commands_send_queue.join_thread()

        log_received_queue.close()
        log_received_queue.join_thread()


        # Stop the computing process
        # if "video" in cfg.features:
        #     try:
        #         if video_stream_process is not None and video_stream_process.is_alive():
        #             video_stream_process.terminate()
        #             logging.info('[AppUI] teminate computing process')
        #             video_stream_process.join(timeout=50)
        #             logging.info('[AppUI] joined computing process')


        #             if video_stream_process.is_alive():
        #                 logging.warning('[AppUI] killing computing process')
        #                 video_stream_process.kill()
        #     except Exception as e:
        #         logging.exception("Exception occured while stopping")


        if "data" in cfg.features:
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

        if "commands" in cfg.features:
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

        try:
            if heatbeat_process is not None and heatbeat_process.is_alive():
                heatbeat_process.terminate()
                logging.info('[AppUI] teminate heartbeat computing process')
                heatbeat_process.join(timeout=50)
                logging.info('[AppUI] joined heartbeat computing process')


                if heatbeat_process.is_alive():
                    logging.warning('[AppUI] killing heartbeat process')
                    heatbeat_process.kill()
        except Exception as e:
            logging.exception("Exception occured while stopping heartbeat")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--conf_path",
        type=str,
        default="config_ui.local.yml",
        help="Path to the config file a config_ui.yml file"
    )

    args = parser.parse_args()
    try:
        cfg = Config(config_path=args.conf_path)

        main()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.exception("Exception occured...")
        raise e
