from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt

from src.ui.button import IconButton

     
class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(80)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }

            QPushButton {
                color: white;
                border: none;
                padding: 10px;
                font-size: 12px;
            }

            QPushButton:hover {
                background-color: #2c3e50;
            }

            QPushButton:pressed {
                background-color: #1abc9c;
            }
        """)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(20)

        self.video_btn = IconButton("src/ui/assets/icons/video.svg", "Video", "video")
        self.map_btn = IconButton("src/ui/assets/icons/map-pin.svg", "Map", "map")
        self.search_btn = IconButton("src/ui/assets/icons/search.svg", "Search", "search")
        self.control_btn = IconButton("src/ui/assets/icons/device-gamepad-3.svg", "Control", "control")

        # connect all signals to ONE handler
        for btn in [self.video_btn, self.map_btn, self.search_btn, self.control_btn]:
            btn.clicked.connect(self.on_click)

        layout.addWidget(self.video_btn)
        layout.addWidget(self.map_btn)
        layout.addWidget(self.search_btn)
        layout.addWidget(self.control_btn)

        self.setLayout(layout)
        
    def on_click(self, key):
        print("Clicked:", key)

        if key == "video":
            self.open_video_menu()

        elif key == "map":
            self.open_map_dialog()

        elif key == "search":
            self.open_search()

        elif key == "control":
            self.open_controls()

    # ---------------- VIDEO MENU ----------------
    def open_video_menu(self):
        menu = QMenu(self)

        menu.addAction("Start Camera")
        menu.addAction("Stop Camera")
        menu.addAction("Record")
        menu.addAction("Snapshot")

        menu.exec(self.mapToGlobal(self.video_btn.pos()))

    # ---------------- MAP DIALOG ----------------
    def open_map_dialog(self):
        QMessageBox.information(self, "Map", "Map dialog opened")

    # ---------------- SEARCH ----------------
    def open_search(self):
        QMessageBox.information(self, "Search", "Search clicked")

    # ---------------- CONTROLS ----------------
    def open_controls(self):
        QMessageBox.information(self, "Controls", "Control panel opened")