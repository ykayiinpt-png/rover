import logging
import multiprocessing
import random
import threading
import time
from datetime import datetime, timezone


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
import pyqtgraph as pg
import numpy as np

# Enable antialiasing for prettier plots
pg.setConfigOptions(antialias=False)

"""
Gray #cecece → rgb(206, 206, 206)
Purple #a559aa → rgb(165, 89, 170)
Teal #59a89c → rgb(89, 168, 156)
Gold #f0c571 → rgb(240, 197, 113)
Red #e02b35 → rgb(224, 43, 53)
Dark Blue #082a54 → rgb(8, 42, 84)
"""

class UltraSoundsCharts(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.draw_lock = threading.Lock()
        
        layout = QVBoxLayout()
        
        # Temperature vs time dynamic plot
        self.plots_graph_grid = pg.GraphicsLayoutWidget()   
        self.plots_graph_grid.setBackground("#1E1E1E")
        
        sensors_positions = ["f", "b", "l", "r"]
        
        pen_width = 1
        self.pens = {
            "f": pg.mkPen(color="#4EC9B0", width=pen_width),
            "b": pg.mkPen(color="#DCDCAA", width=pen_width),
            "l": pg.mkPen(color="#C586C0", width=pen_width),
            "r": pg.mkPen(color="#B5CEA8", width=pen_width)
        }
        styles = {"color": "white", "font-size": "10px"}
        #self.plot_graph.setLabel("left", "cm", **styles)
        #self.plot_graph.setLabel("bottom", "Time (s)", **styles)
        
        
        self.plot_graphs = {}
        for pos, k in enumerate(sensors_positions):
            self.plot_graphs[k] = self.plots_graph_grid.addPlot(row=pos, col=0)
            
            self.plot_graphs[k].setLabel("left", "cm", **styles)
            self.plot_graphs[k].setLabel("bottom", "time (ms)", **styles)
            self.plot_graphs[k].showGrid(x=True, y=True)
            self.plot_graphs[k].setTitle(f"<span style='font-size: 9px'>Ultrasound - {k.upper()}</span>")
            #self.plot_graphs[k].setYRange(0, 150)
            self.plot_graphs[k].setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
            
        
        time_now = datetime.now(timezone.utc).timestamp()
        self.graph_window_size = 200
        self.time = np.array([time_now - i for i in range(self.graph_window_size)])
        self.distances = {
            "f": np.zeros(self.graph_window_size),
            "b": np.zeros(self.graph_window_size),
            "l": np.zeros(self.graph_window_size),
            "r": np.zeros(self.graph_window_size),
        }
        
        # Get a line reference
        self.lines = {}
        
        for k in ["f", "b", "l", "r"]:
            self.lines[k] = self.plot_graphs[k].plot(
                self.time,
                self.distances[k],
                pen=self.pens[k],
                symbol="+",
                symbolSize=1,
                symbolBrush="b",
            )
        
        layout.addWidget(self.plots_graph_grid)
        
        # Values views
        self.ultrasound_values_label = QLabel(text=self.format_data_to_str(0, 0, 0, 0))
        layout.addWidget(self.ultrasound_values_label)
        
        # 
        
        self.setLayout(layout)
        
        # Add a timer to simulate new temperature measurements
        self.timer = QTimer()
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.slot_update_plot)
        #self.timer.start()
        
    
    def format_data_to_str(self, f, b, l, r):
        return f"F: {f:05.2f} cm | B: {b:05.2f} cm | L: {l:05.2f} cm | R: {r:05.2f} cm"
        
        
    def slot_update_plot(self):
        self.time = np.roll(self.time, -1)
        self.time[-1] = self.time[-2] + 1
        
        for k in ["f", "b", "l", "r"]:
            self.distances[k] = np.roll(self.distances[k], -1)
            self.distances[k][-1] = random.randint(0, 100)
            
            self.lines[k].setData(self.time, self.distances[k])
            
        self.ultrasound_values_label.setText(
            self.format_data_to_str(
                self.distances["f"][-1],
                self.distances["b"][-1],
                self.distances["l"][-1],
                self.distances["r"][-1])
        )
        
    def update_charts(self, dict_arr):
        with self.draw_lock:
            # Update the time array
            if len(dict_arr["f"]) >= self.graph_window_size:
                #self.time = [ dict_arr["time"] + i * dict_arr["batch_dt"]["u"] for i in range(self.graph_window_size)]
                
                self.time = [ datetime.now(timezone.utc).timestamp() - i * dict_arr["batch_dt"]["u"] for i in range(self.graph_window_size)]
                self.time = reversed(self.time)
            else:
                l = len(dict_arr["f"])
                #self.time = np.roll(self.time, len(dict_arr["f"]))
                #self.time[-1] = self.time[-1] + dict_arr["batch_dt"]["u"]
                
                self.time[:-l] = self.time[l:]
                self.time[-l:] = self.time[-l-1] + np.arange(1, l+1) * dict_arr["batch_dt"]["u"]
            
            # Update sensors data plot
            for k in ["f", "b", "l", "r"]:
                l = len(dict_arr[k])
                if l >= self.graph_window_size:
                    self.distances[k][:] = dict_arr[k][-self.window_size:]
                else:
                    self.distances[k][:-l] = self.distances[k][l:]
                    self.distances[k][-l:] = dict_arr[k]
                    
                print("After Cropped", len(self.distances[k]))
                
                self.lines[k].setData(self.time, self.distances[k])
        
            self.ultrasound_values_label.setText(
                self.format_data_to_str(
                    self.distances["f"][-1],
                    self.distances["b"][-1],
                    self.distances["l"][-1],
                    self.distances["r"][-1])
            )

        
    def stop(self):
        self.timer.stop()
        try:
            self.draw_lock.release()
            self.draw_lock.release_lock()
        except Exception as e:
            pass
        

class SensorsChartSignals(QObject):
    ultra_sounds_data = pyqtSignal(dict)
    
class SensorsChartsContorller(QThread):
    def __init__(self, data_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.signals = SensorsChartSignals()
        self.stop_event = threading.Event()
        
        self.data_queue = data_queue
        
    def run(self):
        while not self.stop_event.is_set():
            if not self.data_queue.empty():
                data = self.data_queue.get()
                print("Data in Widget: ", data)
                
                if type(data) is dict:
                    for k in data.keys():
                        if k in ["f", "b", "l", "r"]:
                            if type(data[k]) is not list:
                                data[k] = [data[k]]
                                
                            # Convert from metter to centimer
                            data[k] = list(map(lambda x: x*100, data[k]))
                
                self.signals.ultra_sounds_data.emit(data)
            else:
                #print("Queue in Qthread is empty")
                pass
                
            # TODO revieww the timeR
            time.sleep(0.0001)
        logging.info("[SensorsChartsContorller] Thread ended")
    
    def stop(self):
        logging.info("QThread stop fired")
        self.stop_event.set()

class SensorCharts(QWidget):
    def __init__(self, data_queue: multiprocessing.Queue,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Objects
        self.controller = SensorsChartsContorller(data_queue=data_queue)
        
        # Views
        layout = QVBoxLayout()
        
        # Wdigets'
        self.ultrasounds_widget = UltraSoundsCharts()
        self.ultrasounds_widget.setFixedWidth(300)
        
        layout.addWidget(self.ultrasounds_widget)
        
        # bindings
        self.controller.signals.ultra_sounds_data.connect(self.slot_update_utltra_sounds_chart)
        
        self.setLayout(layout)
        
        # Run
        self.controller.start()
        
    def stop(self):
        self.ultrasounds_widget.stop()
        
        self.controller.stop()
        self.controller.signals.ultra_sounds_data.disconnect(self.slot_update_utltra_sounds_chart)
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()
        
        try:
            self.controller.signals.image.disconnect()
        except Exception:
            pass
        
    def slot_update_utltra_sounds_chart(self, data: dict):
        print("Data in slot", data)
        self.ultrasounds_widget.update_charts(data)
        