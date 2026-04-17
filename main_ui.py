import logging
import multiprocessing
import sys

from PyQt6.QtWidgets import QApplication

from src.ui import MainWindow
from src.ui.camera import CameraAsyncProcess
from src.ui.video.process import VstreamClientProcess


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

#logging.getLogger("aioice").setLevel(logging.DEBUG)
#logging.getLogger("aiortc").setLevel(logging.DEBUG)

def main():
    video_frame_compute_result_queue = None
    processor_process = None

    try:
        video_frame_compute_result_queue = multiprocessing.Queue(maxsize=1000)
        app = QApplication(sys.argv)

        window = MainWindow(video_frame_compute_result_queue=video_frame_compute_result_queue)
        
        # Start the video frame processing
        processor_process =  VstreamClientProcess(compute_result_queue=video_frame_compute_result_queue) # RtcTrackClientProcess(compute_result_queue=result_queue)
        processor_process.start()
        
        window.show()

        app.exec()
    except Exception:
        logging.exception("Exception while running main app")
        raise
    finally:
        print("In finally")
        # Stop the computing process
        try:
            processor_process.terminate()
            logging.info('[RtcTrackWidget] teminate computing process')
            processor_process.join(timeout=50)
            logging.info('[RtcTrackWidget] joined computing process')


            if processor_process.is_alive():
                logging.warning('[RtcTrackWidget] killing computing process')
                processor_process.kill()   
        except Exception as e:
            logging.exception("Exception occured while stopping")
    
    
        video_frame_compute_result_queue.close()
        video_frame_compute_result_queue.join_thread()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.exception("Exception occured...")
        raise e