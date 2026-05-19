import logging
import multiprocessing
import sys
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QApplication
)
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import QDateTime, QObject, QThread, pyqtSignal

class LogController(QThread):
    def __init__(self, log_receved_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.signals = LogEmitter()
        
        self.log_receved_queue = log_receved_queue
        
        self.stop_event = multiprocessing.Event()
    
    def run(self):
        while not self.stop_event.is_set():
            # Handle Imu data
            if not self.log_receved_queue.empty():
                data = self.log_receved_queue.get()
                
                self.signals.log_signal.emit(data["level"], data["msg"])
            else:
                #print("Queue in Qthread is empty")
                pass
                
            # TODO revieww the timeR
            time.sleep(0.0001)
    
    def stop(self):
        logging.info("[VelocityWidget] QThread stop fired")
        self.stop_event.set()
        

class LogWidget(QWidget):
    def __init__(self, log_received_queue: multiprocessing.Queue):
        super().__init__()
        self.setWindowTitle("Log Console")
        self.setFixedSize(250, 240)
        
        self.controller = LogController(
            log_receved_queue=log_received_queue
        )
        self.record_log_lock = multiprocessing.Lock()

        layout = QVBoxLayout()

        # Log display
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # Clear button
        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.clicked.connect(self.clear_logs)

        layout.addWidget(self.log_box)
        layout.addWidget(self.clear_btn)

        self.setLayout(layout)

        self.setStyleSheet("""
            QTextEdit {
                background-color: #e1e1e1;
                color: black;
                font-family: Consolas;
                font-size: 12px;
            }
            QPushButton {
                background-color: white;
                color: black;
                padding: 6px;
                border-radius: 5px;
                border-color: black
            }
            QPushButton:pressed {
                background-color: gray;
            }
        """)
        
        #handler = QtLogHandler(self)
        #formatter = logging.Formatter(
        #    "%(asctime)s [%(levelname)s] %(message)s"
        #)
        #handler.setFormatter(formatter)

        #logger = logging.getLogger()
        #logger.addHandler(handler)
        
        self.controller.signals.log_signal.connect(self.slot_record_log)
        self.controller.start()

    def log(self, message, level="INFO"):
        time = QDateTime.currentDateTime().toString("hh:mm:ss")

        color = {
            "INFO": "black",
            "WARN": "#f1c40f",
            "ERROR": "#e74c3c"
        }.get(level, "black")

        formatted = f'<span style="color:{color}">[{time}] [{level}] {message}</span>'

        self.log_box.append(formatted)

        # auto-scroll
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)

    def clear_logs(self):
        with self.record_log_lock:
            self.log_box.clear()
        
    def slot_record_log(self, level, msg):
        with self.record_log_lock:
            self.log(msg, level)
        
    def stop(self):
        try:
            self.record_log_lock.release()
            self.record_log_lock.release_lock()
        except Exception as e:
            pass
        
        self.controller.stop()
        
        try:
            self.controller.signals.log_signal.disconnect(self.slot_record_log)
            self.controller.signals.log_signal.disconnect()
        except Exception:
            pass
        
        self.controller.requestInterruption()
        self.controller.quit()
        self.controller.wait()

class LogEmitter(QObject):
    log_signal = pyqtSignal(str, str)


class QtLogHandler(logging.Handler):
    def __init__(self, widget: LogWidget):
        super().__init__()
        self.emitter = LogEmitter()
        self.emitter.log_signal.connect(widget.log)

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.emitter.log_signal.emit(msg, record.levelname.upper())
