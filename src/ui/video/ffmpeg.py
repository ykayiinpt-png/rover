import logging
import sys
import time
import av
import numpy as np

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QObject, QSize, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

class FfmpegSignals(QObject):
    frame_ready = pyqtSignal(np.ndarray)

class FfmpegStreamController(QThread):
    def __init__(self, stream_url: str):
        super().__init__()
        self.running = True
        self.stream_url = stream_url
        self.container = None
        
        self.signals = FfmpegSignals()
        
        
    def run(self):
        try:
            self.container = av.open(
                self.stream_url,
                format="mpegts",
                options={
                    # LOW LATENCY
                    "fflags": "nobuffer",
                    "flags": "low_delay",
                    "framedrop": "1",

                    # IMPORTANT FOR UDP
                    "probesize": "32",
                    "analyzeduration": "0",
                    "max_delay": "0",
                },
            )

            # IMPORTANT: do NOT manually manage stream decoding
            video_stream = self.container.streams.video[0]

            for packet in self.container.demux(video_stream):

                if not self.running:
                    break

                try:
                    for frame in packet.decode():

                        if not self.running:
                            break

                        # Convert to RGB (Qt-friendly)
                        img = frame.to_ndarray(format="rgb24")

                        # Emit latest frame only
                        self.signals.frame_ready.emit(img)

                except Exception:
                    logging.exception("Exception")
                    # Ignore corrupted UDP packets
                    continue
                
            # TODO: Check if we do need one here
            time.sleep(0.01)

        except Exception as e:
            print("Stream error:", e)

        finally:
            if self.container:
                self.container.close()

    def stop(self):
        self.running = False


class FfmpegVideaoStreamWidget(QWidget):
    def __init__(self, stream_url: str, enabled: bool=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Objects
        """
        Frame processor result queue
        """
        
        self.controller = FfmpegStreamController(stream_url=stream_url)
        
        # Views
        layout = QVBoxLayout()
        
        self.raw_image_track_label = QLabel(
            text="Waiting for track..." if enabled else "Disabled"
        )
        self.raw_image_track_label.setFixedSize(QSize(320, 240))
        self.raw_image_track_label.setStyleSheet("border: 2px solid #555555; border-radius: 5px;")
        
        layout.addWidget(QLabel(text="Camera"))
        layout.addSpacing(3)
        layout.addWidget(self.raw_image_track_label)
        layout.addSpacing(6)
        
        # Bindings
        self.controller.signals.frame_ready.connect(self.update_frame)
        
        self.setLayout(layout)
        
        # Run
        if enabled:
            pass
        
        self.controller.start()
        
    def update_frame(self, frame):
        h, w, ch = frame.shape

        bytes_per_line = ch * w

        qimg = QImage(
            frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )

        # FASTEST POSSIBLE QLabel RENDER
        pixmap = QPixmap.fromImage(qimg)

        self.raw_image_track_label.setPixmap(pixmap)
        
    
    def stop(self):
        self.controller.stop()
        print("Controller stopped")
        
        try:
            self.controller.signals.frame_ready.disconnect(self.update_frame)
            self.controller.signals.frame_ready.disconnect()
        except Exception:
            pass
        
        print("Quiiting FFmpeg")
        self.controller.requestInterruption()
        print("Requset passed")
        self.controller.quit()
        print("Quit Passed")
        self.controller.wait(1000)
        print("Quitted")
