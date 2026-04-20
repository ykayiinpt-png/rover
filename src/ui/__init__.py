import logging
import multiprocessing

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QToolBar, QVBoxLayout, QWidget

from src.ui.detection import DetectionWidget
from src.ui.graphics.map.map_navigation import MapNavigationDialog, MapNavigationWidget
from src.ui.graphics.controls.joystick import KeyboardJoystickDialog
from src.ui.log import LogWidget
from src.ui.graphics.map.map import MapWidget
from src.ui.graphics.sensors.charts import SensorCharts
from src.ui.menus import AccquisitionMenuSensorsParameters
from src.ui.sidebar import Sidebar
from src.ui.video.widgets import RtcTrackWidget


class MainWindow(QMainWindow):
    def __init__(self,
                video_frame_compute_result_queue: multiprocessing.Queue,
                sensors_data_queue: multiprocessing.Queue, map_data_queue: multiprocessing.Queue,
                commands_send_queue: multiprocessing.Queue, commands_receive_queue: multiprocessing.Queue):
        super().__init__()
        
        # Objects
        self.keyboard_joystick_dialog = KeyboardJoystickDialog(
            commands_send_queue=commands_send_queue
        )
        
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
        #self.sidebar = Sidebar()
        #layout.addWidget(self.sidebar)
        
        toolbar = QToolBar("Toolbar")
        #self.addToolBar(toolbar)
        
        menu = self.menuBar()
        
        data_acq_menu = menu.addMenu("Acquisition")
        data_acq_menu_sensors_menus = data_acq_menu.addMenu("Sensors")
        data_acq_menu_sensors_menus_parameter_action = QAction("Parameters", self)
        data_acq_menu_sensors_menus_parameter_action.triggered.connect(self.slot_menu_acq_parameter)
        data_acq_menu_sensors_menus.addAction(data_acq_menu_sensors_menus_parameter_action)
        
        data_acq_menu_video_m = data_acq_menu.addMenu("Video")
        data_acq_menu_video_m_start_track_action = QAction("Start Track", self)
        data_acq_menu_video_m_start_track_action.triggered.connect(self.slot_menu_acq_video_start_track)
        data_acq_menu_video_m_stop_track_action = QAction("Stop Track", self)
        data_acq_menu_video_m_stop_track_action.triggered.connect(self.slot_menu_acq_video_stop_track)
        data_acq_menu_video_m_start_processing_action = QAction("Start Track Processing", self)
        data_acq_menu_video_m_start_processing_action.triggered.connect(self.slot_menu_acq_video_start_track_processing)
        data_acq_menu_video_m_stop_processing_action = QAction("Stop Track Processing", self)
        data_acq_menu_video_m_stop_processing_action.triggered.connect(self.slot_menu_acq_video_stop_track_processing)
        data_acq_menu_video_m_object_detection_action = QAction("Object Detection", self)
        
        data_acq_menu_video_m.addAction(data_acq_menu_video_m_start_track_action)
        data_acq_menu_video_m.addAction(data_acq_menu_video_m_stop_track_action)
        data_acq_menu_video_m.addAction(data_acq_menu_video_m_start_processing_action)
        data_acq_menu_video_m.addAction(data_acq_menu_video_m_stop_processing_action)
        data_acq_menu_video_m.addSeparator()        
        data_acq_menu_video_m.addAction(data_acq_menu_video_m_object_detection_action)
        
        
        
        
        map_menu = menu.addMenu("Map")
        map_menu_open_full_action = QAction("Open Full Map", self)
        map_menu_open_full_action.triggered.connect(self.slop_map_menu_open_full_map)
        map_menu_joystick_action = QAction("Joystick", self)
        map_menu_joystick_action.triggered.connect(self.slop_map_menu_open_joystick)
        map_menu_parameters_action = QAction("Paramètres", self)
        
        map_menu.addAction(map_menu_open_full_action)
        map_menu.addAction(map_menu_joystick_action)
        map_menu.addAction(map_menu_parameters_action)
        
        
        settings_action = menu.addMenu("Paramètres")
        
        
        self.container.setLayout(layout)
        
    def closeEvent(self, event):
        """
        We stop Process here
        """
        logging.info("Closing Application UI")
        self.rtc_track_widget.stop()
        self.sensors_chart.stop()
        
        event.accept()
        
    def slot_menu_acq_parameter(self):
        self.dialog = AccquisitionMenuSensorsParameters()
        if self.dialog.exec():
            data = self.dialog.get_selected_options()
            print(data)
            self.dialog = None # Clear the reference
            
    def slot_menu_acq_video_start_track(self):
        # TODO Check if not already running
        pass
        
    def slot_menu_acq_video_stop_track(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmation")
        msg.setText("Do you want to proceed?")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        print(msg.exec(), QMessageBox.StandardButton.Yes)
        
    def slot_menu_acq_video_start_track_processing(self):
        # TODO Check if not already running
        pass
        
    def slot_menu_acq_video_stop_track_processing(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmation")
        msg.setText("Do you want to proceed?")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        print(msg.exec(), QMessageBox.StandardButton.Yes)
        
    
    def slop_map_menu_open_full_map(self):
        map_navig = MapNavigationDialog()
        map_navig.exec()
        
    def slop_map_menu_open_joystick(self):
        if self.keyboard_joystick_dialog is not None:
            self.keyboard_joystick_dialog.show()
        
        