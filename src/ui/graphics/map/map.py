import sys
import numpy as np
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QImage

class MapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(640, 240)
        self.setMouseTracking(True)

        # ---------------- MAP ----------------
        self.map = np.random.randint(0, 255, (240, 640), dtype=np.uint8)

        # ---------------- CAMERA ----------------
        self.zoom = 1.0
        self.offset = QPointF(0, 0)   # pan in screen space
        self.last_mouse = None

        # ---------------- LAYERS ----------------
        self.show_map = True
        self.show_shapes = True
        self.show_path = True
        self.show_robot = True

        # ---------------- PATH (WORLD COORDS) ----------------
        self.path = []
        self.robot_pos = QPointF(150, 150)

        # ---------------- TIMER (simulate movement) ----------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(100)
        
    def ipoint(p: QPointF):
        return int(p.x()), int(p.y())

    # =========================================================
    # SIMULATION
    # =========================================================
    def update_simulation(self):
        # move robot in world space
        self.robot_pos += QPointF(2, 1.5)

        # store path
        self.path.append(QPointF(self.robot_pos))

        if len(self.path) > 500:
            self.path.pop(0)

        self.update()

    # =========================================================
    # WORLD <-> SCREEN TRANSFORM
    # =========================================================
    def world_to_screen(self, p: QPointF):
        x = p.x() * self.zoom + self.offset.x()
        y = p.y() * self.zoom + self.offset.y()
        return QPointF(x, y)

    def screen_to_world(self, p: QPointF):
        x = (p.x() - self.offset.x()) / self.zoom
        y = (p.y() - self.offset.y()) / self.zoom
        return QPointF(x, y)

    # =========================================================
    # INPUT: PAN
    # =========================================================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse = event.position()

    def mouseMoveEvent(self, event):
        if self.last_mouse is not None:
            delta = event.position() - self.last_mouse
            self.offset += delta
            self.last_mouse = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self.last_mouse = None

    # =========================================================
    # INPUT: ZOOM
    # =========================================================
    def wheelEvent(self, event):
        zoom_factor = 1.15

        if event.angleDelta().y() > 0:
            self.zoom *= zoom_factor
        else:
            self.zoom /= zoom_factor

        self.zoom = max(0.2, min(5.0, self.zoom))
        self.update()

    # =========================================================
    # DRAW
    # =========================================================
    def scale_point(self, x, y):
        sx = self.width() / self.map.shape[1]
        sy = self.height() / self.map.shape[0]
        return int(x * sx), int(y * sy)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ================= MAP LAYER =================
        if self.show_map:
            h, w = self.map.shape
            print((h, w))
            print(int(w * self.zoom), int(h * self.zoom))
            image = QImage(self.map.data, w, h, w, QImage.Format.Format_Grayscale8)

            # TODO: Be reviewed later
            self.zoom = 1
            
            scaled = image.scaled(
                int(w * self.zoom),
                int(h * self.zoom),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

            painter.drawImage(self.offset, scaled)

        # ================= SHAPES LAYER =================
        if self.show_shapes:
            painter.setPen(QPen(Qt.GlobalColor.red, 2))

            # circle (world coords)
            c = self.world_to_screen(QPointF(80, 80))
            painter.drawEllipse(int(c.x()), int(c.y()), int(80 * self.zoom), int(80 * self.zoom))

            # segment
            p1 = self.world_to_screen(QPointF(0, 0))
            p2 = self.world_to_screen(QPointF(300, 300))
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))
            painter.drawLine(p1, p2)

            # square
            s = self.world_to_screen(QPointF(200, 50))
            painter.setPen(QPen(Qt.GlobalColor.green, 2))
            painter.setBrush(QBrush(QColor(0, 255, 0, 80)))
            painter.drawRect(int(s.x()), int(s.y()), int(60 * self.zoom), int(60 * self.zoom))

        # ================= PATH LAYER =================
        if self.show_path and len(self.path) > 1:
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2))

            for i in range(len(self.path) - 1):
                p1 = self.world_to_screen(self.path[i])
                p2 = self.world_to_screen(self.path[i + 1])
                painter.drawLine(p1, p2)

        # ================= ROBOT LAYER =================
        if self.show_robot:
            r = self.world_to_screen(self.robot_pos)

            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(r.x()) - 6, int(r.y()) - 6, 12, 12)
            
# ---------- RUN ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MapWidget()
    w.show()
    sys.exit(app.exec())