import logging

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QWidget

from src.ui.video.widgets import RtcTrackWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Rover SLAM")
        
        self.container = QWidget()
        self.setCentralWidget(self.container)
        
        layout = QHBoxLayout()
        
        # Components
        self.rtc_track_widget = RtcTrackWidget(parent=self)
        layout.addWidget(self.rtc_track_widget)
        
        self.container.setLayout(layout)
        
    def closeEvent(self, event):
        """
        We stop Process here
        """
        logging.info("Closing Application UI")
        self.rtc_track_widget.stop()
        
        event.accept()
        