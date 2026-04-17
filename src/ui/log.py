import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QApplication
)
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import QDateTime


class LogWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Console")
        self.setFixedSize(320, 240)

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
                background-color: #1e1e1e;
                color: #dcdcdc;
                font-family: Consolas;
                font-size: 12px;
            }
            QPushButton {
                background-color: #2c3e50;
                color: white;
                padding: 6px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #1abc9c;
            }
        """)

    # ---------------- LOGGING ----------------

    def log(self, message, level="INFO"):
        time = QDateTime.currentDateTime().toString("hh:mm:ss")

        color = {
            "INFO": "#ffffff",
            "WARN": "#f1c40f",
            "ERROR": "#e74c3c"
        }.get(level, "#ffffff")

        formatted = f'<span style="color:{color}">[{time}] [{level}] {message}</span>'

        self.log_box.append(formatted)

        # auto-scroll
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)

    def clear_logs(self):
        self.log_box.clear()
