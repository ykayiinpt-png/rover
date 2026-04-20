import random

from PyQt6.QtWidgets import QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QImage

from src.ui.graphics.map.map import MapWidget
from src.ui.graphics.map.map_grid import MapGridWidget


class MapNavigationDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setWindowTitle("Acquisition - Sensors Parameters")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        main_layout = QVBoxLayout()
        
        map = MapNavigationWidget()
        main_layout.addWidget(map)
        
        
        self.setLayout(main_layout)
        


class MapNavigationWidget(QWidget):
    """
    Combines the grid map and free map and add a controls
    panel at the left
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        layout = QHBoxLayout()
        
        # Maps
        map_layout = QVBoxLayout()
        pos_map = MapWidget()
        grid_map = MapGridWidget()
        
        map_layout.addWidget(pos_map)
        map_layout.addSpacing(10)
        map_layout.addWidget(grid_map)
        
        layout.addLayout(map_layout)
        
        # Controls
        control_widget = ControlPanel()
        layout.addSpacing(10)
        layout.addWidget(control_widget)
        
        self.setLayout(layout)
        
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

        self.cb_grid = QCheckBox("Show Grid")
        self.cb_robot = QCheckBox("Show Robot")
        self.cb_path = QCheckBox("Show Path")
        self.cb_obstacles = QCheckBox("Show Obstacles")

        for cb in [self.cb_grid, self.cb_robot, self.cb_path, self.cb_obstacles]:
            cb.setChecked(True)
            map_layout.addWidget(cb)

        layout.addWidget(map_section)

        # ================= PATH SECTION =================
        path_section = QFrame()
        path_section.setFrameShape(QFrame.Shape.Box)
        path_layout = QVBoxLayout(path_section)

        path_layout.addWidget(QLabel("PATH SETTINGS"))

        self.start_input = QLineEdit("5,5")
        self.goal_input = QLineEdit("15,20")

        path_layout.addWidget(QLabel("Start (i,j)"))
        path_layout.addWidget(self.start_input)

        path_layout.addWidget(QLabel("Goal (i,j)"))
        path_layout.addWidget(self.goal_input)

        btn_gen = QPushButton("Generate Obstacles")
        btn_astar = QPushButton("Compute A*")

        #btn_gen.clicked.connect(self.map.generate_obstacles)
        #btn_astar.clicked.connect(self.compute_path)

        path_layout.addWidget(btn_gen)
        path_layout.addWidget(btn_astar)

        layout.addWidget(path_section)

        layout.addStretch()