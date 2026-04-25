from datetime import datetime, timezone
import logging
import multiprocessing
import sys
import threading
import time
import numpy as np
from collections import deque
from PyQt6.QtWidgets import QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
import pyqtgraph as pg


class ZRotationWidget(pg.GraphicsLayoutWidget):
    """
    Capture the rotation of the sytem around the z-axis
    """
    
    def __init__(self):
        super().__init__()

        self.plot = self.addPlot()
        self.plot.setAspectLocked()
        self.plot.hideAxis('left')
        self.plot.hideAxis('bottom')
        self.setBackground("#1E1E1E")
        #self.plot.hideAxes()

        # arc demi cercle
        theta = np.linspace(0, 2*np.pi, 100)
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


class SensorsChartSignals(QObject):
    imu = pyqtSignal(dict)
    odometry = pyqtSignal(dict)
    
class StateVelocityContorller(QThread):
    def __init__(self, 
                imu_data_queue: multiprocessing.Queue,
                odometry_data_queue: multiprocessing.Queue,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.signals = SensorsChartSignals()
        self.stop_event = threading.Event()
        
        self.imu_data_queue = imu_data_queue
        self.odometry_data_queue = odometry_data_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Handle Imu data
            if not self.imu_data_queue.empty():
                data = self.imu_data_queue.get()
                print("Data in IMU velocity Widget: ", data)
                
                if type(data) is dict:
                    for k in data.keys():
                        # z - axis velocity
                        # rot - rotation in the rover system
                        if k in ["z", "rot"]:
                            if type(data[k]) is not list:
                                data[k] = [data[k]]
                
                self.signals.imu.emit(data)
            else:
                #print("Queue in Qthread is empty")
                pass
            
            # Handle the odometry queue
            if not self.odometry_data_queue.empty():
                data = self.odometry_data_queue.get()
                print("Data in ODOMETRY velocity Widget: ", data)
                
                if type(data) is dict:
                    for k in data.keys():
                        # w{l,r}_t the left and the right target
                        # w{l,r}_v the left and the right current velocity
                        if k in ["wl_t", "wr_t", "wl_v", "wr_v"]:
                            if type(data[k]) is not list:
                                data[k] = [data[k]]
                
                self.signals.odometry.emit(data)
            else:
                #print("Queue in Qthread is empty")
                pass
                
            # TODO revieww the timeR
            time.sleep(0.0001)
        logging.info("[StateVelocityContorller] Thread ended")
    
    def stop(self):
        logging.info("[VelocityWidget] QThread stop fired")
        self.stop_event.set()

class RobotVelocityStateWidget(QWidget):
    """
    Plot the target velocity and the current velocity
    applied to the both wheel of the system
    """
    
    def __init__(self, 
                imu_data_queue: multiprocessing.Queue,
                odometry_data_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Objects
        self.controller = StateVelocityContorller(
            imu_data_queue=imu_data_queue,
            odometry_data_queue=odometry_data_queue
        )
        self.draw_lock = threading.Lock()
        
        layout = QHBoxLayout(self)

        # ===== LEFT COLUMN =====
        left_layout = QVBoxLayout()

        styles = {"color": "white", "font-size": "10px" }
        # plot principal
        self.main_plot = pg.PlotWidget(title="X-Axis Velocity")
        self.main_plot.setFixedWidth(400)
        self.main_plot.setFixedHeight(250)
        self.main_plot.setLabel("left", "m/s", **styles)
        self.main_plot.setLabel("bottom", "time (ms)", **styles)
        self.main_plot.setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
            
        self.main_plot.setBackground("#1E1E1E")
        self.x_axis_accl_curve = self.main_plot.plot(pen='c')

        left_layout.addWidget(self.main_plot)

        # gauge
        self.gauge = ZRotationWidget()
        self.gauge.setFixedWidth(400)
        self.gauge.setFixedHeight(250)
        left_layout.addWidget(self.gauge)

        # ===== Middle COLUMN =====
        middle_layout = QVBoxLayout()

        self.plot1 = pg.PlotWidget(title="Wheel L")
        self.plot1.setFixedWidth(400)
        self.plot1.setFixedHeight(250)
        self.plot1.setBackground("#1E1E1E")
        self.plot1.addLegend()
        self.plot1.setLabel("left", "m/s", **styles)
        self.plot1.setLabel("bottom", "time (ms)", **styles)
        self.plot1.setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
        self.wheel_left_command = self.plot1.plot(pen='r', name="Command")
        self.wheel_left_target = self.plot1.plot(pen='g', name="Target")
        self.plot1_label = QLabel(self, text="--")

        self.plot2 = pg.PlotWidget(title="Wheel R")
        self.plot2.setFixedWidth(400)
        self.plot2.setFixedHeight(250)
        self.plot2.setBackground("#1E1E1E")
        self.plot2.addLegend()
        self.plot2.setLabel("left", "m/s", **styles)
        self.plot2.setLabel("bottom", "time (ms)", **styles)
        self.plot2.setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
        self.wheel_right_command = self.plot2.plot(pen='y', name="Command")
        self.wheel_right_target = self.plot2.plot(pen='m', name="Target")
        self.plot2_label = QLabel(self, text="--")


        middle_layout.addWidget(self.plot1, alignment=Qt.AlignmentFlag.AlignHCenter)
        middle_layout.addWidget(self.plot1_label)
        middle_layout.addWidget(self.plot2, alignment=Qt.AlignmentFlag.AlignHCenter)
        middle_layout.addWidget(self.plot2_label)
        
        
        # ===== Right COLUMN =====
        right_layout = QVBoxLayout()

        self.plot3 = pg.PlotWidget(title="PWM=100Hz Duty Cycle Left")
        self.plot3.setFixedWidth(400)
        self.plot3.setFixedHeight(250)
        self.plot3.setBackground("#1E1E1E")
        self.plot3.addLegend()
        self.plot3.setLabel("left", "%", **styles)
        self.plot3.setLabel("bottom", "time (ms)", **styles)
        self.plot3.setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
        self.pwm_left_plot = self.plot3.plot(pen='r')
        self.plot3_label = QLabel(self, text="--")


        self.plot4 = pg.PlotWidget(title="PWM=100Hz Duty Cycle Right")
        self.plot4.setFixedWidth(400)
        self.plot4.setFixedHeight(250)
        self.plot4.setBackground("#1E1E1E")
        self.plot4.addLegend()
        self.plot4.setLabel("left", "m/s", **styles)
        self.plot4.setLabel("bottom", "time (ms)", **styles)
        self.plot4.setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
        self.pwm_right_plot = self.plot4.plot(pen='g', name="Right")
        self.plot4_label = QLabel(self, text="--")


        right_layout.addWidget(self.plot3)
        right_layout.addWidget(self.plot3_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        right_layout.addWidget(self.plot4)
        right_layout.addWidget(self.plot4_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addLayout(left_layout)
        layout.addLayout(middle_layout)
        layout.addLayout(right_layout)
        

        # ===== DATA =====
        self.maxlen = 2000
        time_now = datetime.now(timezone.utc).timestamp()
        self.x_imu_time = deque([time_now - i for i in range(self.maxlen)], maxlen=self.maxlen)
        self.x_odometry_time = self.x_imu_time.copy()

        self.y_accel_x = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)

        self.y_wl_t = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)
        self.y_wl_c = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)

        self.y_wr_t = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)
        self.y_wr_c = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)
        
        self.y_wl_p = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)
        self.y_wr_p = deque(np.zeros(shape=self.maxlen), maxlen=self.maxlen)

        self.t = 0

        # timer animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        #self.timer.start(50)
        
        self.controller.signals.imu.connect(self.slot_update_rotation_chart)
        self.controller.signals.odometry.connect(self.slot_update_wlr_chart)
        
        self.controller.start()
        
    def stop(self):
        self.timer.stop()
        
        try:
            self.draw_lock.release()
            self.draw_lock.release_lock()
        except Exception as e:
            pass
        
        self.controller.stop()
        try:
            self.controller.signals.imu.disconnect(self.slot_update_rotation_chart)
            self.controller.signals.odometry.disconnect(self.slot_update_wlr_chart)
            self.controller.signals.disconnect()
        except Exception as e:
            pass
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()
        
    def slot_update_wlr_chart(self, data: dict):
        """
        Update the velocity
        charts of right and left wheels
        """        
        with self.draw_lock:
            self.x_odometry_time.extend(self.x_odometry_time[-1] +  np.arange(1, len(data["wl_t"])+1) * data["batch_dt"]["ax"])
            
            self.y_wl_t.extend(data["wl_t"])
            self.y_wl_c.extend(data["wl_c"])
            
            self.y_wr_t.extend(data["wr_t"])
            self.y_wr_c.extend(data["wr_c"])
            
            self.y_wl_p.extend(data["wl_p"])
            self.y_wr_p.extend(data["wr_p"])
            
            self.plot1_label.setText(f"T={self.y_wl_t[-1]:05.2f} C={self.y_wl_c[-1]:05.2f} Error={(self.y_wl_t[-1] - self.y_wl_c[-1]):05.2f}")
            self.plot2_label.setText(f"T={self.y_wr_t[-1]:05.2f} C={self.y_wr_c[-1]:05.2f} Error={(self.y_wr_t[-1] - self.y_wr_c[-1]):05.2f}")
            self.plot3_label.setText(f"DutyCycle={self.y_wl_p[-1]:05.2f}")
            self.plot4_label.setText(f"DutyCycle={self.y_wr_p[-1]:05.2f}")
            
            # Draw
            self.wheel_left_command.setData(self.x_odometry_time, self.y_wl_c)
            self.wheel_left_target.setData(self.x_odometry_time, self.y_wl_t)

            self.wheel_right_command.setData(self.x_odometry_time, self.y_wr_c)
            self.wheel_right_target.setData(self.x_odometry_time, self.y_wr_t)
            
            self.pwm_right_plot.setData(self.x_odometry_time, self.y_wr_p)
            self.pwm_left_plot.setData(self.x_odometry_time, self.y_wl_p)
           

    def slot_update_rotation_chart(self, data: dict):
        """
        Update the rotationnary angle
        """
        with self.draw_lock:
            self.x_imu_time.extend(self.x_imu_time[-1] + np.arange(1, len(data["a_x"])+1) * data["batch_dt"]["ax"])
            
            self.y_accel_x.extend(data["a_x"])
            
            # Draw
            self.x_axis_accl_curve.setData(self.x_imu_time, self.y_accel_x)
            self.gauge.update_gauge(0, data["rot"][-1]) # Just the last value


    def update(self):
        """
        @deprecated
        """
        
        self.t += 0.1

        # génération données
        x_val = self.t
        y_z = np.sin(self.t)

        y1 = np.sin(self.t * 1.2)
        y2 = np.cos(self.t * 0.8)

        y3 = np.sin(self.t * 0.5)
        y4 = np.cos(self.t * 1.5)

        # append
        self.x.append(x_val)
        self.y_accel_x.append(y_z)

        self.y_wl_t.append(y1)
        self.y_wl_c.append(y2)

        self.y_wr_t.append(y3)
        self.y_wr_c.append(y4)

        # update plots
        self.x_axis_accl_curve.setData(self.x, self.y_accel_x)

        self.wheel_left_command.setData(self.x, self.y_wl_t)
        self.wheel_left_target.setData(self.x, self.y_wl_c)

        self.wheel_right_command.setData(self.x, self.y_wr_t)
        self.wheel_right_target.setData(self.x, self.y_wr_c)

        # angles pour gauge
        angle1 = (np.sin(self.t) + 1) / 2 * np.pi
        angle2 = (np.cos(self.t) + 1) / 2 * np.pi

        self.gauge.update_gauge(angle1, angle2)

class RobotVelocityStateDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)