import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt


class DetectionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO Detections")
        self.setFixedSize(320, 240)

        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels([
            "Class", "Confidence", "X", "Y", "Box (W×H)", "ID",
        ])

        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)
        self.setLayout(layout)

        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: white;
                gridline-color: #444;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
            }
        """)

    # --------------------------------------------------
    # UPDATE DETECTIONS
    # --------------------------------------------------
    def update_detections(self, detections):
        """
        detections format:
        [
            {"class": "person", "conf": 0.87, "x": 120, "y": 80, "w": 60, "h": 150},
            ...
        ]
        """

        self.table.setRowCount(len(detections))

        for row, det in enumerate(detections):
            self.table.setItem(row, 0, QTableWidgetItem(det["class"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{det['conf']:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(str(det["x"])))
            self.table.setItem(row, 3, QTableWidgetItem(str(det["y"])))
            self.table.setItem(row, 4, QTableWidgetItem(f"{det['w']}×{det['h']}"))
            