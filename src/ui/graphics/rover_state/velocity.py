import sys
import numpy as np
from collections import deque
from PyQt6.QtWidgets import QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer
import pyqtgraph as pg


class ZRotationWidget(pg.GraphicsLayoutWidget):
    def __init__(self):
        super().__init__()

        self.plot = self.addPlot()
        self.plot.setAspectLocked()
        self.setBackground("#1E1E1E")
        #self.plot.hideAxes()

        # arc demi cercle
        theta = np.linspace(0, np.pi, 100)
        self.x_arc = np.cos(theta)
        self.y_arc = np.sin(theta)
        self.plot.plot(self.x_arc, self.y_arc, pen=pg.mkPen(width=2))

        # aiguilles
        self.needle1 = self.plot.plot([0, 1], [0, 0], pen=pg.mkPen('r', width=3))
        self.needle2 = self.plot.plot([0, 1], [0, 0], pen=pg.mkPen('y', width=3))

        self.label = pg.TextItem("", anchor=(0.5, 0))
        self.plot.addItem(self.label)
        self.label.setPos(0, -0.2)

    def update_gauge(self, angle1, angle2):
        # angles entre 0 et pi
        x1, y1 = np.cos(angle1), np.sin(angle1)
        x2, y2 = np.cos(angle2), np.sin(angle2)

        self.needle1.setData([0, x1], [0, y1])
        self.needle2.setData([0, x2], [0, y2])

        direction = "Clockwise" if angle2 > angle1 else "CounterClockwise"
        self.label.setText(direction)


class RobotVelocityStateWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Rover State - Velocity")
        layout = QHBoxLayout(self)

        # ===== LEFT COLUMN =====
        left_layout = QVBoxLayout()

        # plot principal
        self.main_plot = pg.PlotWidget(title="Main Curve")
        self.main_plot.setBackground("#1E1E1E")
        self.curve = self.main_plot.plot(pen='c')

        left_layout.addWidget(self.main_plot)

        # gauge
        self.gauge = ZRotationWidget()
        left_layout.addWidget(self.gauge)

        # ===== RIGHT COLUMN =====
        right_layout = QVBoxLayout()

        self.plot1 = pg.PlotWidget(title="Velocity Wheel Left")
        self.wheel_left_command = self.plot1.plot(pen='r')
        self.plot1.setBackground("#1E1E1E")
        self.wheel_left_target = self.plot1.plot(pen='g')

        self.plot2 = pg.PlotWidget(title="Velocity Wheel Right")
        self.plot2.setBackground("#1E1E1E")
        self.wheel_right_command = self.plot2.plot(pen='y')
        self.wheel_right_target = self.plot2.plot(pen='m')

        right_layout.addWidget(self.plot1)
        right_layout.addWidget(self.plot2)

        layout.addLayout(left_layout)
        layout.addLayout(right_layout)

        # ===== DATA =====
        self.maxlen = 200
        self.x = deque(maxlen=self.maxlen)

        self.y_main = deque(maxlen=self.maxlen)

        self.y1_1 = deque(maxlen=self.maxlen)
        self.y1_2 = deque(maxlen=self.maxlen)

        self.y2_1 = deque(maxlen=self.maxlen)
        self.y2_2 = deque(maxlen=self.maxlen)

        self.t = 0

        # timer animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def update(self):
        self.t += 0.1

        # génération données
        x_val = self.t
        y_main = np.sin(self.t)

        y1 = np.sin(self.t * 1.2)
        y2 = np.cos(self.t * 0.8)

        y3 = np.sin(self.t * 0.5)
        y4 = np.cos(self.t * 1.5)

        # append
        self.x.append(x_val)
        self.y_main.append(y_main)

        self.y1_1.append(y1)
        self.y1_2.append(y2)

        self.y2_1.append(y3)
        self.y2_2.append(y4)

        # update plots
        self.curve.setData(self.x, self.y_main)

        self.wheel_left_command.setData(self.x, self.y1_1)
        self.wheel_left_target.setData(self.x, self.y1_2)

        self.wheel_right_command.setData(self.x, self.y2_1)
        self.wheel_right_target.setData(self.x, self.y2_2)

        # angles pour gauge
        angle1 = (np.sin(self.t) + 1) / 2 * np.pi
        angle2 = (np.cos(self.t) + 1) / 2 * np.pi

        self.gauge.update_gauge(angle1, angle2)

class RobotVelocityStateDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)