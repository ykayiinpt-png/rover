import sys
import threading

from PyQt6.QtWidgets import (
    QApplication, QDialog, QLabel, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPalette, QPen, QBrush, QImage, QPixmap, QPolygonF
import cv2

from src.ai.pipeline import TrackedObject
from src.core.shared import MemorySharedDict


class DetectionWidget(QWidget):
    def __init__(self, app_state: MemorySharedDict):
        super().__init__()
        self.setWindowTitle("YOLO Detections")
        self.setFixedSize(270, 240)

        self.app_state = app_state

        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(6)

        self.draw_lock = threading.Lock()
        self.tracks: dict[int, TrackedObject] = {}

        self.table.setHorizontalHeaderLabels([
            "Class", "Confidence", "X", "Y", "Box (W×H)", "Track ID"
        ])

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        # row click event
        self.table.cellClicked.connect(
            self.slot_on_row_clicked
        )

        layout.addWidget(self.table)
        self.setLayout(layout)

        self.setStyleSheet("""
            QTableWidget {
                background-color: #white;
                color: black;
                gridline-color: #444;
            }
            QHeaderView::section {
                background-color: white;
                color: black;
            }
        """)

        self.timer = QTimer()
        self.timer.timeout.connect(self.slot_check_for_objects_update)

        self.timer.start(1000)

    def stop(self):
        self.timer.stop()

        try:
            self.draw_lock.release()
        except Exception:
            pass

    def slot_check_for_objects_update(self):
        if self.app_state["ia_objects_available"]:
            self.tracks = self.app_state["ia_objects"]

            tracks = self.tracks.values()
            with self.draw_lock:
                self.table.setRowCount(len(tracks))

                for row, track in enumerate(tracks):
                    self.table.setItem(row, 0, QTableWidgetItem(track.class_name))
                    self.table.setItem(row, 1, QTableWidgetItem(f"{track.confidence:.2f}"))
                    self.table.setItem(row, 2, QTableWidgetItem(str(0)))
                    self.table.setItem(row, 3, QTableWidgetItem(str(0)))
                    self.table.setItem(row, 4, QTableWidgetItem(f"{track.bbox}"))
                    self.table.setItem(row, 5, QTableWidgetItem(f"{track.id}"))
        else:
            pass


    def slot_on_row_clicked(self, row, column):
        track_id_item = self.table.item(row, 5)

        if track_id_item is None:
            return

        track_id = int(track_id_item.text())
        track = self.tracks.get(track_id)

        if track is None:
            return

        if track.bbox_image is None:
            return

        self.show_image_dialog(track)

    def show_image_dialog(self, track):

        dialog = QDialog(self)

        dialog.setWindowTitle(
            f"Track {track.id} - {track.class_name}"
        )

        layout = QVBoxLayout(dialog)

        image_label = QLabel()

        image = track.bbox_image

        # convert BGR -> RGB
        rgb_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        qt_image = QImage(
            rgb_image.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )

        pixmap = QPixmap.fromImage(qt_image)
        image_label.setPixmap(pixmap)

        image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(image_label)
        dialog.resize(300, 300)
        dialog.exec()
