import multiprocessing
import sys
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QWidget, QApplication
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor


class KeyboardJoystickDialog(QDialog):
    def __init__(self, commands_send_queue: multiprocessing.Queue,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Joystick")
        layout = QHBoxLayout()
        
        w = KeyboardJoystickWidget(commands_send_queue=commands_send_queue)
        layout.addWidget(w)
        
        self.setLayout(layout)

class KeyboardJoystickWidget(QWidget):
    # Emits raw direction string
    directionChanged = pyqtSignal(str)
    directionReleased = pyqtSignal(str)

    # Emits joystick-like axis (x, y)
    axisChanged = pyqtSignal(float, float)

    def __init__(self, commands_send_queue: multiprocessing.Queue,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Objects
        self.commands_send_queue = commands_send_queue
        
        
        self.setFixedSize(220, 220)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Track pressed keys (for continuous + combos)
        self.pressed_keys = set()

        self.key_map = {
            Qt.Key.Key_I: "front",
            Qt.Key.Key_K: "back",
            Qt.Key.Key_J: "left",
            Qt.Key.Key_L: "right",
            Qt.Key.Key_Space: "stop",
        }

        # Timer for continuous signal
        self.timer = QTimer()
        self.timer.timeout.connect(self.emit_continuous)
        self.timer.start(100)  # every 100ms

        # STOP button
        self.stop_btn = QPushButton("S", self)
        self.stop_btn.setGeometry(95, 95, 30, 30)
        self.stop_btn.clicked.connect(self.handle_stop)

        self.apply_style()

    def apply_style(self):
        self.setStyleSheet("""
            QPushButton {
                border-radius: 15px;
                background-color: #c0392b;
                color: white;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #e74c3c;
            }
        """)

    # ---------- INPUT HANDLING ----------

    def keyPressEvent(self, event):
        key = event.key()

        if key in self.key_map:
            if key == Qt.Key.Key_Space:
                self.handle_stop()
                return

            self.pressed_keys.add(key)
            self.update()

    def keyReleaseEvent(self, event):
        key = event.key()

        if key in self.key_map:
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)
                self.update()

    def handle_stop(self):
        self.pressed_keys.clear()
        self.directionChanged.emit("stop")
        self.axisChanged.emit(0.0, 0.0)
        
        self.commands_send_queue.put({
            "topic": "slam/commands/raspberry",
            "payload": {"x": 0, "y": 0, "a": "stop"}
        })
        
        print("STOP")
        self.update()

    # ---------- CONTINUOUS EMIT ----------

    def emit_continuous(self):
        x, y = 0.0, 0.0

        if Qt.Key.Key_I in self.pressed_keys:
            y += 1
        if Qt.Key.Key_K in self.pressed_keys:
            y -= 1
        if Qt.Key.Key_J in self.pressed_keys:
            x -= 1
        if Qt.Key.Key_L in self.pressed_keys:
            x += 1

        # Normalize diagonal speed
        if x != 0 and y != 0:
            x *= 0.707
            y *= 0.707

        # Emit axis (REAL joystick behavior)
        self.axisChanged.emit(x, y)

        # Emit simple direction (optional)
        if x == 0 and y == 0:
            return
        
        self.commands_send_queue.put({
            "topic": "slam/commands/raspberry",
            "payload": {"x": x, "y": y, "a": "move"}
        })

        direction = f"x={x:.2f}, y={y:.2f}"
        print(direction)
        self.directionChanged.emit(direction)

    # ---------- DRAW UI ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() // 2
        center_y = self.height() // 2
        size = 50
        offset = 75

        def active(keys):
            return any(k in self.pressed_keys for k in keys)

        def draw_circle(x, y, label, keys):
            color = QColor("#1abc9c") if active(keys) else QColor("#2c3e50")
            painter.setBrush(color)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawEllipse(x, y, size, size)
            painter.drawText(x, y, size, size, Qt.AlignmentFlag.AlignCenter, label)

        draw_circle(center_x - size//2, center_y - offset, "I", [Qt.Key.Key_I])
        draw_circle(center_x - size//2, center_y + offset - size, "K", [Qt.Key.Key_K])
        draw_circle(center_x - offset, center_y - size//2, "J", [Qt.Key.Key_J])
        draw_circle(center_x + offset - size, center_y - size//2, "L", [Qt.Key.Key_L])