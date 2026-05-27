import logging
import sys
import time

import cv2
import av
import numpy as np

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QObject, QSize, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from src.ai.pipeline import ObjectDetectionPipeline
from src.core.shared import MemorySharedDict
from src.raspberry.config import Config

class FfmpegSignals(QObject):
    frame_ready = pyqtSignal(np.ndarray)

class FfmpegStreamController(QThread):
    def __init__(self, stream_url: str, app_state: MemorySharedDict):
        super().__init__()
        self.running = True
        self.stream_url = stream_url
        self.container = None

        self.signals = FfmpegSignals()

        self.app_state = app_state

        self.cfg = Config()

        # Pipelines
        self.pipeline_object_detection = ObjectDetectionPipeline(
            classes=self.cfg.ai.pipelines.object_detection.classes,
            conf_threshold=self.cfg.ai.pipelines.object_detection.confidence.threshold,
            draw_boxes=self.cfg.ai.pipelines.object_detection.draw_boxes,
            frame_rate=self.cfg.ai.pipelines.object_detection.frame.rate,
            model_name=self.cfg.ai.pipelines.object_detection.model.name,
        )


    def run(self):
        try:
            prev_time = time.time()
            fps = 0.0
            frame_count = 0

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

                        frame_count += 1
                        current_time = time.time()

                        if current_time - prev_time >= 1.0:
                            fps = frame_count / (current_time - prev_time)
                            prev_time = current_time
                            frame_count = 0



                        # Convert to RGB (Qt-friendly)
                        frame = frame.to_ndarray(format="rgb24")

                        if self.cfg.ai.pipelines.object_detection.enabled:
                            frame, objects = self.pipeline_object_detection.process(frame)
                            #print("Objects Yolo: ", objects)

                            try:
                                has_data = len(objects) > 0
                                if has_data:
                                    self.app_state["ia_objects"] = self.pipeline_object_detection.tracker.tracks
                                    self.app_state["ia_objects_available"] = has_data
                            except Exception:
                                logging.exception("Exception while writing ai detected objects")



                        #################""
                        # Write FPS
                        text = f"FPS: {fps:.1f}"

                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.5
                        thickness = 1

                        (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)

                        x = frame.shape[1] - text_w - 10   # top-right padding
                        y = 30

                        cv2.putText(frame, text, (x, y), font, font_scale,
                             (0, 255, 0), thickness, cv2.LINE_AA
                         )

                        # Emit latest frame only
                        self.signals.frame_ready.emit(frame)

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


class FfmpegVideoStreamWidget(QWidget):
    def __init__(self, stream_url: str,  app_state: MemorySharedDict, enabled: bool=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Objects
        """
        Frame processor result queue
        """

        self.controller = FfmpegStreamController(stream_url=stream_url, app_state=app_state)

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

        logging.info("[FfmpedVideoStream] Quiiting FFmpeg")
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait(200)
