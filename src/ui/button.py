from PyQt6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QPushButton
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, pyqtSignal

class IconButton(QWidget):
    
    clicked = pyqtSignal(str)
    
    def __init__(self, icon_path, text, key):
        super().__init__()
        
        self.key = key

        self.setObjectName("iconButton")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedSize(80, 90)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn = QPushButton()
        self.btn.setFixedSize(50, 50)
        self.btn.setIcon(QIcon(icon_path))
        self.btn.setIconSize(self.btn.size())

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 11px;")

        layout.addWidget(self.btn)
        layout.addWidget(self.label)
        
        self.setLayout(layout)
        
        # click handling
        self.btn.clicked.connect(self.emit_clicked)

        self.setStyleSheet("""
            root {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
        """)

        self.btn.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            border: none;
        }""")
        
    def emit_clicked(self):
        self.clicked.emit(self.key)
    
    # ---------------- HOVER ENTER ----------------
    def enterEvent(self, event):
        self.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                border-radius: 10px;
            }
        """)
        super().enterEvent(event)

    # ---------------- HOVER LEAVE ----------------
    def leaveEvent(self, event):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
        """)
        super().leaveEvent(event)
  