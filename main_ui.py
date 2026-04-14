import logging

from PyQt6.QtWidgets import QApplication

from src.ui import MainWindow
from src.ui.camera import CameraAsyncProcess


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    app = QApplication([])
    
    # Camera processing 
    camera = CameraAsyncProcess()
    camera.start()
    logging.info("Camera process started")

    window = MainWindow()
    window.show()

    app.exec()
    
    # A the end
    print("Stopping camera process")
    #camera.terminate()
    camera.stop()
    camera.join()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.exception("Exception occured...")
        raise e