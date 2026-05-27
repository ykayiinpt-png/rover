import logging
import multiprocessing
import random

from PyQt6.QtWidgets import QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QImage

from src.ui.graphics.map.map import MapGridWidget, MapControlWidget

class MapNavigationControlWidget(QWidget):
    """
    Combines the grid map and free map and add a controls
    panel at the left
    """

    def __init__(self, grid_map: MapGridWidget, command_sent_data_queue: multiprocessing.Queue,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Mapping Navigation Control")

        layout = QHBoxLayout()

        self.grid_map = grid_map
        self.computed_waypoints = None
        self.command_sent_data_queue = command_sent_data_queue

        # Maps
        map_layout = QVBoxLayout()
        map_layout.addWidget(grid_map)

        layout.addLayout(map_layout)

        # Controls
        self.control_widget = ControlPanel()
        layout.addSpacing(10)
        layout.addWidget(self.control_widget)

        self.setLayout(layout)

        self.control_widget.btn_apply_threshold.clicked.connect(self.slot_apply_threshold_on_grid)
        self.control_widget.btn_astar.clicked.connect(self.slot_compute_path_to_goal)
        self.control_widget.btn_run_waypoints.clicked.connect(self.slot_send_waypoint_to_robot)
        self.control_widget.btn_reset_grid.clicked.connect(self.slot_reset_grid)

        self.control_widget.cb_robot_path.toggled.connect(self.slot_handle_cb_robot_path)
        self.control_widget.cb_followed_path.toggled.connect(self.slot_handle_cb_navigation_robot_path)
        self.control_widget.cb_planned_path.toggled.connect(self.slot_handle_cb_robot_planned_path)

        self.grid_map.signals.grid_cell_clicked.connect(self.slot_path_destination_clicked)


    def slot_handle_cb_robot_path(self, v):
        self.grid_map.show_robot_path = v

    def slot_handle_cb_robot_planned_path(self, v):
        self.grid_map.show_planned_robot_path= v

    def slot_handle_cb_navigation_robot_path(self, v):
        self.grid_map.show_navigation_robot_path = v


    def slot_apply_threshold_on_grid(self):
        pass

    def slot_reset_grid(self):
        self.grid_map.reset()

    def slot_path_destination_clicked(self, x, y):
        self.control_widget.goal_input.setText(f"{x},{y}")

    def slot_compute_path_to_goal(self):
        goal_point = self.control_widget.goal_input.text()

        try:
            self.computed_waypoints =  self.grid_map.show_path_to(
                goal=reversed([int(item.strip()) for item in goal_point.split(",")]),
                threshold=float(self.control_widget.threshold_input.text())
             )

        except Exception as e:
            logging.exception("[MapNavigationControl] Exception occured")

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)  # Set the icon to "Error"
            msg.setWindowTitle("Error")
            msg.setText("Something went wrong!")
            msg.setInformativeText("Please check your input and try again. " + f"\n\n{e}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

    def slot_send_waypoint_to_robot(self):
        if self.computed_waypoints is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)  # Set the icon to "Error"
            msg.setWindowTitle("Error")
            msg.setText("Something went wrong!")
            msg.setInformativeText("No ways has been computed")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
        else:
            try:
                self.command_sent_data_queue.put({
                    "topic": "slam/rover/commands/remote",
                    "payload":  {"type": "navigation", "data": self.computed_waypoints}
                })
            except Exception as e:
                logging.exception("[MapNavigationControl] Exception occured")

                msg = QMessageBox()
                msg.setIcon(QMessageBox.Icon.Critical)  # Set the icon to "Error"
                msg.setWindowTitle("Error")
                msg.setText("Something went wrong!")
                msg.setInformativeText("Please check your input and try again. " + f"\n\n{e}")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()



    def closeEvent(self, a0):
        print("Closed")
        return super().closeEvent(a0)


class ControlPanel(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout(self)

        # ================= MAP SECTION =================
        map_section = QFrame()
        map_section.setFrameShape(QFrame.Shape.Box)
        map_layout = QVBoxLayout(map_section)

        map_layout.addWidget(QLabel("MAP CONTROLS"))

        self.cb_robot_path = QCheckBox("Show Robot Path")
        self.cb_planned_path = QCheckBox("Show Planned Path")
        self.cb_followed_path = QCheckBox("Show Folled Path")

        for cb in [self.cb_robot_path, self.cb_planned_path, self.cb_followed_path]:
            cb.setChecked(True)
            map_layout.addWidget(cb)

        self.btn_reset_grid = QPushButton("Reset Grid")
        map_layout.addWidget(self.btn_reset_grid)

        layout.addWidget(map_section)

        # ================= PATH SECTION =================
        path_section = QFrame()
        path_section.setFrameShape(QFrame.Shape.Box)
        path_layout = QVBoxLayout(path_section)

        path_layout.addWidget(QLabel("PATH SETTINGS"))

        self.goal_input = QLineEdit("15,20")
        self.threshold_input = QLineEdit("1")

        path_layout.addWidget(QLabel("Goal (i,j)"))
        path_layout.addWidget(self.goal_input)

        path_layout.addWidget(QLabel("Occupancy Treshold"))
        path_layout.addWidget(self.threshold_input)

        self.btn_apply_threshold = QPushButton("Apply Treshold")
        self.btn_astar = QPushButton("Compute A*")
        self.btn_run_waypoints = QPushButton("Run WayPoint")

        path_layout.addWidget(self.btn_apply_threshold)
        path_layout.addSpacing(5)
        path_layout.addWidget(self.btn_astar)
        path_layout.addSpacing(15)
        path_layout.addWidget(self.btn_run_waypoints)

        layout.addWidget(path_section)

        layout.addStretch()
