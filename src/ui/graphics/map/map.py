import collections
import logging
import multiprocessing
import random
import sys
import threading
import time
from typing import Deque
import numpy as np
import numpy as np
import pyqtgraph as pg
import matplotlib.cm as cm
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget, QApplication
from PyQt6.QtCore import QObject, QThread, Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPalette, QPen, QBrush, QImage, QPolygonF

from src.core.search import astar


class MapSignals(QObject):
    position = pyqtSignal(tuple)
    mapping_position = pyqtSignal(tuple)
    
class MapStateController(QThread):
    def __init__(self,
                 map_data_queue: multiprocessing.Queue, 
                 mapping_position_data_queue: multiprocessing.Queue,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.signals = MapSignals()
        self.stop_event = threading.Event()
        self.map_data_queue = map_data_queue
        self.mapping_position_data_queue = mapping_position_data_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Handle Imu data
            if not self.map_data_queue.empty():
                data = self.map_data_queue.get()
                #print("Map data", data)
                self.signals.position.emit((data["x"], data["y"], data["dist"]))
                
            if not self.mapping_position_data_queue.empty():
                data = self.mapping_position_data_queue.get()
                #print("Mapping Data data", data)
                self.signals.mapping_position.emit((data["x"], data["y"], data["theta"]))
            
            time.sleep(0.01)
        logging.info("[MapStateController] Thread ended")
        
    def stop(self):
        logging.info("[MapStateController] QThread stop fired")
        self.stop_event.set()

class MapWidgetQtPaint(QWidget):
    """
    @deprecated
    """
    
    def __init__(self, 
                 map_data_queue: multiprocessing.Queue,
                 mapping_position_data_queue: multiprocessing.Queue,
                 path_max_size=500, *args, **kwargs):
        """
        :param path_max_size:
        """
        
        super().__init__(*args, **kwargs)
        self.setFixedSize(440, 240)
        self.setMouseTracking(True)
        
        # Objects
        self.controller = MapStateController(
            map_data_queue=map_data_queue,
            mapping_position_data_queue=mapping_position_data_queue
        )
        self.draw_lock = threading.Lock()
        
        # Map size
        self.map_w = 440
        self.map_h = 240

        # ---------------- MAP ----------------
        self.map = np.ones((self.map_h, self.map_w), dtype=np.uint8) * 255

        # ---------------- CAMERA ----------------
        self.zoom = 1.0
        self.offset = QPointF(0, 0)   # pan in screen space
        self.last_mouse = None

        # ---------------- LAYERS ----------------
        self.show_map = False
        self.show_shapes = False
        self.show_path = True
        self.show_robot = True
        self.show_distance_text = True

        # ---------------- PATH (WORLD COORDS) ----------------
        self.path: Deque[QPointF] = collections.deque(maxlen=path_max_size)
        self.path_polygon = QPolygonF()
        self.robot_pos = QPointF(0, 0)
        self.distance_text = "0.00 m"
        
        self.path_ekf: Deque[QPointF] = collections.deque(maxlen=path_max_size)
        self.path_ekf_polygon = QPolygonF()
        self.robot_ekf_pos = QPointF(0, 0)

        # ---------------- TIMER (simulate movement) ----------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        #self.timer.start(100)
        
        self.controller.signals.position.connect(self.slot_update_position)
        self.controller.signals.mapping_position.connect(self.slot_update_mapping_position)
        self.controller.start()
        
    def ipoint(p: QPointF):
        return int(p.x()), int(p.y())

    # =========================================================
    # SIMULATION
    # =========================================================
    def update_simulation(self):
        # move robot in world space
        self.robot_pos += QPointF(2, -1.5)

        # store path
        self.path.append(QPointF(self.robot_pos))

        self.update()
        
    def slot_update_position(self, position_data):
        x, y, dist = position_data
        with self.draw_lock:
            #print("Update position")
            for k in range(len(x)):
                self.robot_pos = QPointF(x[k] * 10, y[k]*10)
                
                self.path_polygon.append(
                    self.world_to_screen(self.robot_pos)
                )
                
                self.path.append(self.robot_pos)
                self.distance_text = f"{dist[k]:05.2f}"
            
            self.update()
            
    def slot_update_mapping_position(self, position_data):
        x, y, _ = position_data
        with self.draw_lock:
            #print("Update position")
            for k in range(len(x)):
                self.robot_ekf_pos = QPointF(x[k]*10, y[k]*10)
                
                self.path_ekf_polygon.append(
                    self.world_to_screen(self.robot_ekf_pos)
                )
                
                self.path_ekf.append(self.robot_ekf_pos)
            self.update()
            
    def clear_robot_path(self):
        """
        Remove all previous robot position appended to the path
        drawn on the screen
        """
        
        with self.draw_lock:
            self.path.clear()
            self.path_ekf.clear()
            self.path_polygon.clear()
            self.path_ekf_polygon.clear()
            self.robot_pos = QPointF(0, 0)
            self.robot_ekf_pos = QPointF(0, 0)
            self.update()
    
    def stop(self):
        self.timer.stop()
        
        try:
            self.draw_lock.release()
            self.draw_lock.release_lock()
        except Exception as e:
            pass
        
        self.controller.stop()
        try:
            self.controller.signals.position.disconnect(self.slot_update_position)
            self.controller.signals.mapping_position.disconnect(self.slot_update_mapping_position)
            self.controller.signals.disconnect()
        except Exception as e:
            pass
        
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()

    # =========================================================
    # WORLD <-> SCREEN TRANSFORM
    # =========================================================
    def world_to_screen(self, p: QPointF) -> QPointF:
        """
        Convert world coordinates to widget/screen coordinates.

        World coordinates:
            - origin at map center
            - +x -> right
            - +y -> up

        Screen coordinates:
            - origin at top-left
            - +x -> right
            - +y -> down
        """

        x = (
            self.width() / 2
            + (p.x() * self.zoom)
            + self.offset.x()
        )

        y = (
            self.height() / 2
            - (p.y() * self.zoom)
            + self.offset.y()
        )

        return QPointF(x, y)


    def screen_to_world(self, p: QPointF) -> QPointF:
        """
        Convert widget/screen coordinates back to world coordinates.
        """

        x = (
            (p.x() - self.width() / 2 - self.offset.x())
            / self.zoom
        )

        y = (
            -(p.y() - self.height() / 2 - self.offset.y())
            / self.zoom
        )

        return QPointF(x, y)

    # =========================================================
    # INPUT: PAN
    # =========================================================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse = event.position()

    def mouseMoveEvent(self, event):
        if self.last_mouse is not None:
            delta = event.position() - self.last_mouse
            self.offset += delta
            self.last_mouse = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self.last_mouse = None

    # =========================================================
    # INPUT: ZOOM
    # =========================================================
    def wheelEvent(self, event):
        zoom_factor = 1.15

        if event.angleDelta().y() > 0:
            self.zoom *= zoom_factor
        else:
            self.zoom /= zoom_factor

        self.zoom = max(0.2, min(5.0, self.zoom))
        self.update()

    # =========================================================
    # DRAW
    # =========================================================
    def scale_point(self, x, y):
        sx = self.width() / self.map.shape[1]
        sy = self.height() / self.map.shape[0]
        return int(x * sx), int(y * sy)
    

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("black"))
        
        # ================= TEXT =================
        painter.setPen(QPen(QColor("blue")))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            self.distance_text
        )
        
        painter.setPen(QPen(QColor("black")))
        painter.drawText(
            0, 0,
            self.width() - 10, 30,
            Qt.AlignmentFlag.AlignRight,
            "---- Odometry"
        )

        painter.setPen(QPen(QColor("blue")))
        painter.drawText(
            0, 30,
            self.width() - 10, 30,
            Qt.AlignmentFlag.AlignRight,
            "---- EKF"
        )

        # ================= MAP LAYER =================
        if self.show_map:
            h, w = self.map.shape
            #print((h, w))
            #print(int(w * self.zoom), int(h * self.zoom))
            image = QImage(self.map.data, w, h, w, QImage.Format.Format_Grayscale8)

            # TODO: Be reviewed later
            self.zoom = 1
            
            scaled = image.scaled(
                int(w * self.zoom),
                int(h * self.zoom),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

            painter.drawImage(self.offset, scaled)

        # ================= SHAPES LAYER =================
        if self.show_shapes:
            painter.setPen(QPen(Qt.GlobalColor.red, 2))

            # circle (world coords)
            c = self.world_to_screen(QPointF(80, 80))
            painter.drawEllipse(int(c.x()), int(c.y()), int(80 * self.zoom), int(80 * self.zoom))

            # segment
            p1 = self.world_to_screen(QPointF(0, 0))
            p2 = self.world_to_screen(QPointF(300, 300))
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))
            painter.drawLine(p1, p2)

            # square
            s = self.world_to_screen(QPointF(200, 50))
            painter.setPen(QPen(Qt.GlobalColor.green, 2))
            painter.setBrush(QBrush(QColor(0, 255, 0, 80)))
            painter.drawRect(int(s.x()), int(s.y()), int(60 * self.zoom), int(60 * self.zoom))

        # ================= PATH LAYER =================
        if self.show_path and len(self.path) > 1 and len(self.path_ekf) > 1:
            painter.setPen(QPen(Qt.GlobalColor.black, 2))

            #for i in range(len(self.path) - 1):
            #    p1 = self.world_to_screen(self.path[i])
            #    p2 = self.world_to_screen(self.path[i + 1])
            #    painter.drawLine(p1, p2)  
            painter.drawPolyline(self.path_polygon)
            
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))    
            painter.drawPolyline(self.path_ekf_polygon)
            #for i in range(len(self.path_ekf) - 1):
            #    p1 = self.world_to_screen(self.path_ekf[i])
            #    p2 = self.world_to_screen(self.path_ekf[i + 1])
            #    painter.drawLine(p1, p2)

        # ================= ROBOT LAYER =================
        if self.show_robot:
            r = self.world_to_screen(self.robot_pos)

            painter.setBrush(QBrush(QColor(0, 0, 0)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(r.x()) - 6, int(r.y()) - 6, 12, 12)
            
            
            r = self.world_to_screen(self.robot_ekf_pos)

            painter.setBrush(QBrush(QColor(0, 0, 255)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(r.x()) - 6, int(r.y()) - 6, 12, 12)


class MapWidget(QWidget):

    def __init__(self,
                 map_data_queue,
                 mapping_position_data_queue,
                 path_max_size=500,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setMinimumSize(440, 240)

        # ---------------- CONTROLLER ----------------
        self.controller = MapStateController(
            map_data_queue=map_data_queue,
            mapping_position_data_queue=mapping_position_data_queue
        )

        # ---------------- DATA ----------------
        self.path = []
        self.path_ekf = []

        self.robot_pos = (0.0, 0.0)
        self.robot_ekf_pos = (0.0, 0.0)
        self.distance_text = "0.00 m"

        # ---------------- PYQTGRAPH ----------------
        pg.setConfigOptions(useOpenGL=True, antialias=False)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.hideAxis('bottom')
        self.plot.hideAxis('left')
        self.plot.addLegend()

        # Paths (equivalent to your polyline)
        self.path_curve = self.plot.plot(pen=pg.mkPen('k', width=2), name="Odometry")
        self.ekf_curve = self.plot.plot(pen=pg.mkPen('b', width=2), name="EKF")

        # Robot markers (fast scatter)
        self.robot_scatter = pg.ScatterPlotItem(
            size=10,
            brush=pg.mkBrush(0, 0, 0),
        )

        self.ekf_robot_scatter = pg.ScatterPlotItem(
            size=10,
            brush=pg.mkBrush(0, 0, 255),
        )

        self.plot.addItem(self.robot_scatter)
        self.plot.addItem(self.ekf_robot_scatter)

        # ---------------- LAYOUT ----------------
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        # ---------------- SIGNALS ----------------
        self.controller.signals.position.connect(self.slot_update_position)
        self.controller.signals.mapping_position.connect(self.slot_update_mapping_position)
        self.controller.start()

    # =========================================================
    # DATA UPDATE (ODOMETRY)
    # =========================================================
    def slot_update_position(self, position_data):
        x, y, dist = position_data

        for i in range(len(x)):
            self.robot_pos = (x[i] * 10, y[i] * 10)
            self.path.append(self.robot_pos)
            self.distance_text = f"{dist[i]:05.2f}"

        self._refresh_paths()

    # =========================================================
    # DATA UPDATE (EKF)
    # =========================================================
    def slot_update_mapping_position(self, position_data):
        x, y, _ = position_data

        for i in range(len(x)):
            self.robot_ekf_pos = (x[i] * 10, y[i] * 10)
            self.path_ekf.append(self.robot_ekf_pos)

        self._refresh_paths()

    # =========================================================
    # FAST RENDER UPDATE
    # =========================================================
    def _refresh_paths(self):

        if len(self.path) > 1:
            arr = np.asarray(self.path)
            self.path_curve.setData(arr[:, 0], arr[:, 1])

        if len(self.path_ekf) > 1:
            arr = np.asarray(self.path_ekf)
            self.ekf_curve.setData(arr[:, 0], arr[:, 1])

        # robot markers
        self.robot_scatter.setData([self.robot_pos[0]], [self.robot_pos[1]])
        self.ekf_robot_scatter.setData([self.robot_ekf_pos[0]], [self.robot_ekf_pos[1]])

    # =========================================================
    # CLEAR
    # =========================================================
    def clear_robot_path(self):
        self.path = []
        self.path_ekf = []

        self.robot_pos = (0.0, 0.0)
        self.robot_ekf_pos = (0.0, 0.0)

        self.path_curve.setData([], [])
        self.ekf_curve.setData([], [])

        self.robot_scatter.setData([], [])
        self.ekf_robot_scatter.setData([], [])
    
        self._refresh_paths()

    # =========================================================
    # STOP
    # =========================================================
    def stop(self):
        self.controller.stop()
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()
        
class MapControlWidget(QWidget):
    """
    Map Widget with simple interactions controls
    """
    
    
    def __init__(self, map_data_queue: multiprocessing.Queue, 
                 mapping_state_receive_data_queue: multiprocessing.Queue,
                 path_max_size: int,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Map
        self.map_widget = MapWidget(
            map_data_queue=map_data_queue,
            mapping_position_data_queue=mapping_state_receive_data_queue,
            path_max_size=path_max_size
        )
        layout_map = QVBoxLayout()
        layout_btns = QHBoxLayout()
        
        layout_map.addSpacing(10)
        layout_btns.addWidget(QLabel(text="Map"))
        
        reset_map_btn = QPushButton(text="Reset Robot Path")
        reset_map_btn.clicked.connect(self.slot_reset_map)
        layout_btns.addWidget(reset_map_btn)
        
        layout_map.addLayout(layout_btns)
        layout_map.addSpacing(3)
        layout_map.addWidget(self.map_widget)
        
        self.setLayout(layout_map)
        
    def slot_reset_map(self):
        self.map_widget.clear_robot_path()
        
    def stop(self):
        self.map_widget.stop()
        
################################
# Map Grid view
#

class MapGridSignals(QObject):
    grid = pyqtSignal(tuple)
    
class MapGridStateController(QThread):
    def __init__(self,
                 grid_data_queue: multiprocessing.Queue,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.signals = MapGridSignals()
        self.stop_event = threading.Event()
        self.grid_data_queue = grid_data_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Handle Imu data
            if not self.grid_data_queue.empty():
                data = self.grid_data_queue.get()
                self.signals.grid.emit((data["dim"], data["cells"], data["robot"]))
            time.sleep(0.1)
        logging.info("[MapStateController] Thread ended")
    
    def stop(self):
        self.stop_event.set()

class MapGridWidget(QWidget):
    def __init__(self, grid_data_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(490, 490)

        self.controller = MapGridStateController(
            grid_data_queue=grid_data_queue
        )

        self.draw_lock = threading.Lock()

        # ================= GRID CONFIG =================
        self.rows = 70
        self.cols = 70

        self.cell_w = self.width() // self.cols
        self.cell_h = self.height() // self.rows

        # ================= STATIC GRID =================
        self.grid_image = QImage(self.width(), self.height(), QImage.Format.Format_RGB32)
        self.grid_image.fill(QColor(245, 245, 245))
        self.build_static_grid()
        self.cmap = cm.get_cmap("gray")

        # ================= DYNAMIC GRID BUFFER =================
        # 0 = empty
        # 1 = robot
        # 2 = obstacle
        # 3 = path
        # 4 = probability overlay (optional)
        self.grid = [[0.6 for _ in range(self.cols)] for _ in range(self.rows)]

        # ================= ROBOT =================
        self.robot = (0, 0)

        # ================= SIGNAL =================
        self.controller.signals.grid.connect(self.slot_update_grid)
        self.controller.start()

    # =========================================================
    # STATIC GRID
    # =========================================================
    def build_static_grid(self):
        painter = QPainter(self.grid_image)
        painter.setPen(QPen(QColor(0, 0, 0), 1))

        for i in range(self.rows):
            y = i * self.cell_h
            for j in range(self.cols):
                x = j * self.cell_w
                painter.drawRect(x, y, self.cell_w, self.cell_h)

        painter.end()

    def slot_update_grid(self, grid_data):
        dim, data, rb = grid_data
        src_h, src_w = dim

        scale_y = self.rows / src_h
        scale_x = self.cols / src_w
        
        max_val = 5

        with self.draw_lock:
            #print("Gota data do map")
            for x, y, p in data:
                i = int(y * scale_y)
                j = int(x * scale_x)

                if 0 <= i < self.rows and 0 <= j < self.cols:
                    #p = 1 - 1 / (1 + np.exp(p))
                    #self.grid[y][x] = p # min(255, self.grid[i][j] + int(p * 255))
                    #print(x, y, p, 1 - (p + max_val) / (2 * max_val))
                    # Normalize the value
                    self.grid[y][x] = 1 - (p + max_val) / (2 * max_val)
                    
                    #print(self.grid[i][j], int(255 * (1-self.grid[i][j])))
                #print("\n\n")
                    
            self.robot = [rb[0], rb[1]]

        self.update()
        
    def show_path_to(self, goal, threshold):
        """
        Computes a path from the robot position to goal and updates the grid.
        goal: (i,j)
        
        :retuns path list(tuple): the path from the current robot position to
        the destination point
        """
        # Make a copy of the grid for pathfinding (obstacles > 1)
        grid_copy = np.array(self.grid, dtype=float)

        path = astar(grid_copy, self.robot, goal, threshold=threshold)

        if path is None:
            print("No path found")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Information")
            msg.setText("WayPoints")
            msg.setInformativeText("No path has been found")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return None

        with self.draw_lock:
            # mark the path in the grid
            for i, j in path:
                if (i, j) != self.robot:  # don't overwrite robot
                    self.grid[i][j] = 3

        self.update()
        
        return path
    
    def reset(self):
        with self.draw_lock:
            self.grid = [[0.6 for _ in range(self.cols)] for _ in range(self.rows)]
            self.robot = [0, 0]
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.drawImage(0, 0, self.grid_image)
        
        # TODO: Optimize this double for loop

        for i in range(self.rows):
            y = i * self.cell_h
            for j in range(self.cols):
                x = j * self.cell_w
                v = self.grid[i][j]

                if v == -1:
                    continue
                if v == 2000:
                    painter.fillRect(x, y, self.cell_w, self.cell_h, QColor(0, 255, 0))
                elif v == 3000:
                    # Path computed
                    painter.fillRect(x, y, self.cell_w, self.cell_h, QColor(0, 0, 255))
                else:  # probability overlay threshold
                    gray = int(np.clip(v, 0.0, 1.0) * 255)
                    painter.fillRect(
                        x, y, 
                        self.cell_w, self.cell_h,
                        QColor(gray, gray, gray+50, 255)
                    )
                    

        # robot
        ri, rj = self.robot
        painter.fillRect(
            rj * self.cell_w,
            ri * self.cell_h,
            self.cell_w,
            self.cell_h,
            QColor(255, 0, 0)
        )
        
    def stop(self):
        self.controller.stop()
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()
    
