import logging
import multiprocessing

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from src.ui.detection import DetectionWidget
from src.ui.log import LogWidget
from src.ui.graphics.map.map import MapWidget
from src.ui.graphics.sensors.charts import SensorCharts
from src.ui.sidebar import Sidebar
from src.ui.video.widgets import RtcTrackWidget


class MainWindow(QMainWindow):
    def __init__(self,
                video_frame_compute_result_queue: multiprocessing.Queue,
                sensors_data_queue: multiprocessing.Queue, map_data_queue: multiprocessing.Queue):
        super().__init__()
        
        self.setWindowTitle("Rover SLAM")
        
        self.container = QWidget()
        self.setCentralWidget(self.container)
        
        layout = QHBoxLayout()
        
        # Components
        self.sensors_chart = SensorCharts(data_queue=sensors_data_queue)
        layout.addWidget(self.sensors_chart)
        
        self.rtc_track_widget = RtcTrackWidget(parent=self, compute_queue=video_frame_compute_result_queue)
        layout.addWidget(self.rtc_track_widget)
        
        layout_c = QVBoxLayout()
        layout_cb = QHBoxLayout()
        
        self.map_preview_widget = MapWidget()
        layout_map_widget = QVBoxLayout()
        layout_map_widget.addSpacing(10)
        layout_map_widget.addWidget(QLabel(text="Map"))
        layout_map_widget.addSpacing(3)
        layout_map_widget.addWidget(self.map_preview_widget)
        
        layout_c.addLayout(layout_map_widget)
        
        self.detection_objecs_widget =  DetectionWidget()
        layout_do_widget = QVBoxLayout()
        layout_do_widget.addWidget(QLabel(text="Objects"))
        layout_do_widget.addSpacing(1)
        layout_do_widget.addWidget(self.detection_objecs_widget)
        
        layout_cb.addLayout(layout_do_widget)
        
        self.logs_widget = LogWidget()
        layout_logs_widget = QVBoxLayout()
        layout_logs_widget.addWidget(QLabel(text="Logs"))
        layout_logs_widget.addSpacing(3)
        layout_logs_widget.addWidget(self.logs_widget)
        
        layout_cb.addLayout(layout_logs_widget)
        
        layout_c.addLayout(layout_cb)
        layout.addLayout(layout_c)
        
        # The sidebar
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)
        
        self.container.setLayout(layout)
        
    def closeEvent(self, event):
        """
        We stop Process here
        """
        logging.info("Closing Application UI")
        self.rtc_track_widget.stop()
        self.sensors_chart.stop()
        
        event.accept()
        