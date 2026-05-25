import logging
import multiprocessing

from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QToolBar, QVBoxLayout, QWidget

from src.core.shared import MemorySharedDict
from src.ui.detection import DetectionWidget
from src.ui.graphics.map.navigation import MapNavigationControlWidget
from src.ui.graphics.controls.joystick import KeyboardJoystickDialog
from src.ui.graphics.rover_state.velocity import RobotVelocityStateWidget
from src.ui.log import LogWidget
from src.ui.graphics.map.map import MapControlWidget, MapGridWidget, MapWidget
from src.ui.graphics.sensors.charts import SensorCharts
from src.ui.menus import AccquisitionMenuSensorsParameters
from src.ui.sidebar import Sidebar
from src.ui.video.ffmpeg import FfmpegVideaoStreamWidget
from src.ui.video.widgets import RtcTrackWidget

class StatusIndicator(QLabel):
    """
    Status from heartbeat
    """
    
    def __init__(self):
        super().__init__()
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(False)

    def set_status(self, state: bool):
        color = "green" if state else "red"
        self.setStyleSheet(f"""
            background-color: {color};
            border-radius: 10px;
            border: 1px solid black;
        """)

class MainWindow(QMainWindow):
    def __init__(self,
                ui_state: MemorySharedDict,
                video_frame_compute_result_queue: multiprocessing.Queue,
                sensors_ultrasound_data_queue: multiprocessing.Queue,
                sensors_imu_data_queue: multiprocessing.Queue,
                odometry_data_queue: multiprocessing.Queue,
                map_receive_data_queue: multiprocessing.Queue,
                mapping_grid_data_queue: multiprocessing.Queue,
                mapping_state_receive_data_queue: multiprocessing.Queue,
                command_sent_data_queue: multiprocessing.Queue,
                command_receive_data_queue: multiprocessing.Queue,
                
                log_received_queue: multiprocessing.Queue,
                
                video_stream_url:str, video_stream_enabled: bool):
        super().__init__()
        
        #self.bac
        
        # Objects
        self.ui_state = ui_state
        
        self.keyboard_joystick_dialog = KeyboardJoystickDialog(
            commands_send_queue=command_sent_data_queue,
            command_receive_queue=command_receive_data_queue
        )
        
        self.rover_state_velocity = RobotVelocityStateWidget(
            imu_data_queue=sensors_imu_data_queue,
            odometry_data_queue=odometry_data_queue
        )
        
        self.setWindowTitle("Rover SLAM")
        
        self.container = QWidget()
        self.setCentralWidget(self.container)
        
        layout = QHBoxLayout()
        
        # ----- Status Bar -----
        self.status = self.statusBar()
        # Container widget for status bar
        s_container = QWidget()
        s_layout = QHBoxLayout()
        s_layout.setContentsMargins(5, 0, 5, 0)

        self.heartbeat_indicator = StatusIndicator()
        self.heartbeat_text_label = QLabel("Disconnected")

        s_layout.addWidget(self.heartbeat_indicator)
        s_layout.addWidget(self.heartbeat_text_label)

        s_container.setLayout(s_layout)

        self.status.addPermanentWidget(s_container)
        
         # Timer every 100 ms
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.slot_update_status)
        self.heartbeat_timer.start(1)
        # END
        
        # Components
        self.sensors_chart = SensorCharts(data_queue=sensors_ultrasound_data_queue)
        layout.addWidget(self.sensors_chart)
        
        
        # layout_rtc_ang_angle = QVBoxLayout()
        
        # self.rtc_track_widget = RtcTrackWidget(parent=self, compute_queue=video_frame_compute_result_queue)
        # layout_rtc_ang_angle.addWidget(self.rtc_track_widget)
        # layout_rtc_ang_angle.addWidget(QLabel(text="Orientation"))
        # layout_rtc_ang_angle.addSpacing(3)
        # layout_rtc_ang_angle.addWidget(self.rover_state_velocity.gauge)
        #layout.addWidget(self.rtc_track_widget)
        
        layout_video_stream = QVBoxLayout()
        self.ffmpeg_video_streamer_widget = FfmpegVideaoStreamWidget(
            stream_url=video_stream_url, enabled=video_stream_enabled
        )
        print(self.ffmpeg_video_streamer_widget )
        layout_video_stream.addWidget(self.ffmpeg_video_streamer_widget)
        
        layout_video_stream.addWidget(self.rover_state_velocity.gauge)
        
        layout.addLayout(layout_video_stream)
        
        layout_c = QVBoxLayout()
        layout_cb = QHBoxLayout()
        
        # Map
        self.map_preview_widget = MapControlWidget(
            map_data_queue=map_receive_data_queue,
            mapping_state_receive_data_queue=mapping_state_receive_data_queue,
            path_max_size=2000
        )
        layout_c.addWidget(self.map_preview_widget)
        
        self.grid_map = MapGridWidget(
            grid_data_queue=mapping_grid_data_queue
        )
        
        self.map_navig = MapNavigationControlWidget(
            grid_map=self.grid_map,
            command_sent_data_queue=command_sent_data_queue
        )
        
        # Object Detection
        self.detection_objecs_widget =  DetectionWidget()
        layout_do_widget = QVBoxLayout()
        layout_do_widget.addWidget(QLabel(text="Objects"))
        layout_do_widget.addSpacing(1)
        layout_do_widget.addWidget(self.detection_objecs_widget)
        
        layout_cb.addLayout(layout_do_widget)
        
        self.logs_widget = LogWidget(
            log_received_queue=log_received_queue
        )
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
        data_acq_menu_sensors_menus_parameter_action.triggered.connect(self.slot_menu_acq_sensors_parameter)
        data_acq_menu_sensors_menus.addAction(data_acq_menu_sensors_menus_parameter_action)
        
        data_acq_menu_rovstate_menus = data_acq_menu.addMenu("Rover State")
        data_acq_menu_rovstate_menus_velocity_action = QAction("Velocity", self)
        data_acq_menu_rovstate_menus_velocity_action.triggered.connect(self.slot_menu_acq_rstate_velocity)
        data_acq_menu_rovstate_menus.addAction(data_acq_menu_rovstate_menus_velocity_action)
        
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
        
        if self.keyboard_joystick_dialog.isVisible():
            self.keyboard_joystick_dialog.hide()
                
        if self.rover_state_velocity.isVisible():
            self.rover_state_velocity.hide()
            
        if self.grid_map.isVisible():
            self.grid_map.hide()
            
            
        # self.rtc_track_widget.stop()
        self.sensors_chart.stop()
        self.rover_state_velocity.stop()
        self.map_preview_widget.stop()
        self.grid_map.stop()
        self.ffmpeg_video_streamer_widget.stop()
        
        self.logs_widget.stop()
        
        event.accept()
        
    def slot_update_status(self):
        if self.ui_state["alive"]:
            self.heartbeat_indicator.set_status(True)
            self.heartbeat_text_label.setText("Connected")
        else:
            self.heartbeat_indicator.set_status(False)
            self.heartbeat_text_label.setText("Disconnected")
        
    def slot_menu_acq_sensors_parameter(self):
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
        if not self.map_navig.isVisible():
            self.map_navig.show()
        
        
    def slop_map_menu_open_joystick(self):
        if not self.keyboard_joystick_dialog.isVisible():
            self.keyboard_joystick_dialog.show()
            
    def slot_menu_acq_rstate_velocity(self):
        if not self.rover_state_velocity.isVisible():
            self.rover_state_velocity.show()
        
        