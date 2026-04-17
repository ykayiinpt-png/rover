import logging
import multiprocessing
import threading
import time

from PyQt6.QtCore import QSize, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QImage, QPixmap
import numpy as np

from src.ui.video.process import VstreamClientProcess


class RtcTrackSignals(QObject):
    image = pyqtSignal(QImage)

class RtcTrackController(QThread):
    """
    Observe the RTC track and emit UI update with a Qimage
    """
    
    def __init__(self, compute__result_queue: multiprocessing.Queue,  *args, **kwargs):
        """
        :param queue: the computing result queue
        """
        
        super().__init__(*args, **kwargs)
        
        self.signals = RtcTrackSignals(self)
        
        self.compute__result_queue = compute__result_queue
        
        self.stop_event = threading.Event()
        
    def run(self):
        while not self.stop_event.is_set():
            if not self.compute__result_queue.empty():
                # We do have a numpy nd array here
                # TODO: build image and send to image pyqslot
                rgb_frame: np.ndarray = self.compute__result_queue.get()
                print("Frame In Controller Widget: ", rgb_frame.shape)
                
                height, width, channel = rgb_frame.shape
                bytes_per_line = channel * width
                
                q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                self.signals.image.emit(q_img)
            else:
                print("Queue in Qthread is empty")
                
            # TODO revieww the timeR
            time.sleep(1)
            print("QThread running on track video")
        logging.info("[RtcTrackController] Thread ended")
    
    def stop(self):
        logging.info("QThread stop fired")
        self.stop_event.set()


class RtcTrackWidget(QWidget):
    """
    Video track reader from RTC source
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Objects
        """
        Frame processor result queue
        """
        result_queue = multiprocessing.Queue()
        
        self.controller = RtcTrackController(compute__result_queue=result_queue, parent=self)
        
        # Views
        layout = QVBoxLayout()
        
        self.image_track_label = QLabel(text="Waiting for track...")
        self.image_track_label.setFixedSize(QSize(100, 100))
        
        layout.addWidget(self.image_track_label)
        
        # Bindings
        self.controller.signals.image.connect(self.update_frame)
        
        self.setLayout(layout)
        
        # Run
        self.controller.start()
        
        # Start the video frame processing
        self.processor_process =  VstreamClientProcess(compute_result_queue=result_queue) # RtcTrackClientProcess(compute_result_queue=result_queue)
        self.processor_process.start()
        
    
    def stop(self):
        # Stop all launched process here
        self.controller.stop()
        self.controller.signals.image.disconnect(self.update_frame)
        
        try:
            self.controller.signals.image.disconnect()
        except Exception:
            pass
        
        # Stop the computing process
        try:
            self.processor_process.terminate()
            logging.info('[RtcTrackWidget] teminate computing process')
            self.processor_process.join(timeout=50)
            logging.info('[RtcTrackWidget] joined computing process')


            if self.processor_process.is_alive():
                logging.warning('[RtcTrackWidget] killing computing process')
                self.processor_processs.kill()   
        except Exception as e:
            logging.exception("Exception occured while stopping")
        
    
    def update_frame(self, image: QImage):
        try:
            self.image_track_label.setPixmap(QPixmap.fromImage(image))
        except Exception:
            logging.exception("While setting image")