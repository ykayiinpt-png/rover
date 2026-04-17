import argparse
import logging
import multiprocessing
import sys

from PyQt6.QtWidgets import QApplication

from src.ui import MainWindow
from src.ui.video.process import VstreamClientProcess


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

#logging.getLogger("aioice").setLevel(logging.DEBUG)
#logging.getLogger("aiortc").setLevel(logging.DEBUG)

def main(io_url: str):
    video_frame_compute_result_queue = None
    processor_process = None

    try:
        video_frame_compute_result_queue = multiprocessing.Queue(maxsize=1000)
        app = QApplication(sys.argv)

        window = MainWindow(video_frame_compute_result_queue=video_frame_compute_result_queue)
        
        # Start the video frame processing
        #processor_process =  VstreamClientProcess(
        #    compute_result_queue=video_frame_compute_result_queue,
        #    io_url=io_url
        #) 
        # RtcTrackClientProcess(compute_result_queue=result_queue)
        #processor_process.start()
        
        window.show()

        app.exec()
    except Exception:
        logging.exception("Exception while running main app")
        raise
    finally:
        print("In finally")
        # Stop the computing process
        try:
            if processor_process is not None:
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
    parser = argparse.ArgumentParser()
    
    parser.add_argument(
        "--ws_uri",
        type=str,
        default="http://127.0.0.1:8000",
        help="Host (e.g. http://127.0.0.1:8000)"
    )
    
    args = parser.parse_args()
    try:
        main(io_url=args.ws_uri)
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.exception("Exception occured...")
        raise e