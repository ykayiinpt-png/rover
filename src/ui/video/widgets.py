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
    
    def __init__(self, compute_result_queue: multiprocessing.Queue,  *args, **kwargs):
        """
        :param queue: the computing result queue
        """
        
        super().__init__(*args, **kwargs)
        
        self.signals = RtcTrackSignals(self)
        
        self.compute_result_queue = compute_result_queue
        
        self.stop_event = threading.Event()
        
    def run(self):
        while not self.stop_event.is_set():
            if not self.compute_result_queue.empty():
                # We do have a numpy nd array here
                # TODO: build image and send to image pyqslot
                rgb_frame: np.ndarray = self.compute_result_queue.get()
                #print("Frame In Controller Widget: ", rgb_frame.shape)
                
                height, width, channel = rgb_frame.shape
                bytes_per_line = channel * width
                
                q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                self.signals.image.emit(q_img)
            else:
                #print("Queue in Qthread is empty")
                pass
                
            # TODO revieww the timeR
            time.sleep(0.0001)
        logging.info("[RtcTrackController] Thread ended")
    
    def stop(self):
        logging.info("QThread stop fired")
        self.stop_event.set()


class RtcTrackWidget(QWidget):
    """
    Video track reader from RTC source
    """
    
    def __init__(self, compute_queue: multiprocessing.Queue , *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Objects
        """
        Frame processor result queue
        """
        
        self.controller = RtcTrackController(compute_result_queue=compute_queue, parent=self)
        
        # Views
        layout = QVBoxLayout()
        
        self.raw_image_track_label = QLabel(text="Waiting for track...")
        self.raw_image_track_label.setFixedSize(QSize(320, 240))
        self.raw_image_track_label.setStyleSheet("border: 2px solid #555555; border-radius: 5px;")
        
        self.processed_image_track_label = QLabel(text="Waiting for track...")
        self.processed_image_track_label.setFixedSize(QSize(320, 240))
        self.processed_image_track_label.setStyleSheet("border: 2px solid #555555; border-radius: 5px;")
        
        layout.addWidget(QLabel(text="Camera"))
        layout.addSpacing(3)
        layout.addWidget(self.raw_image_track_label)
        layout.addSpacing(6)
        layout.addWidget(QLabel(text="Camera - Processing"))
        layout.addSpacing(3)
        layout.addWidget(self.processed_image_track_label)
        
        # Bindings
        self.controller.signals.image.connect(self.update_frame)
        
        self.setLayout(layout)
        
        # Run
        self.controller.start()
        
    
    def stop(self):
        # Stop all launched process here
        self.controller.stop()
        self.controller.signals.image.disconnect(self.update_frame)
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()
        
        try:
            self.controller.signals.image.disconnect()
        except Exception:
            pass
        
    
    def update_frame(self, image: QImage):
        try:
            self.raw_image_track_label.setPixmap(QPixmap.fromImage(image))
        except Exception:
            logging.exception("While setting image")