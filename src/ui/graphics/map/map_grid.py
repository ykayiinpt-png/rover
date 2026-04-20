import random

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QImage


class MapGridWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(440, 240)

        # ================= GRID CONFIG =================
        self.rows = 20
        self.cols = 30

        self.cell_w = self.width() // self.cols
        self.cell_h = self.height() // self.rows

        # ================= STATIC GRID IMAGE =================
        self.grid_image = QImage(self.width(), self.height(), QImage.Format.Format_RGB32)
        self.grid_image.fill(QColor(245, 245, 245))
        self.build_static_grid()

        # ================= DYNAMIC CELLS =================
        # (i, j) -> state
        # 1 = robot, 2 = obstacle, 3 = path
        self.cells = {}

        # ================= ROBOT =================
        self.robot = (10, 10)

        # ================= OBSTACLES =================
        for _ in range(80):
            i = random.randint(0, self.rows - 1)
            j = random.randint(0, self.cols - 1)
            self.cells[(i, j)] = 2

        # ================= TIMER =================
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(200)

    # =========================================================
    # BUILD STATIC GRID (DONE ONCE)
    # =========================================================
    def build_static_grid(self):
        painter = QPainter(self.grid_image)

        pen = QPen(QColor(200, 200, 200), 1)
        painter.setPen(pen)

        for i in range(self.rows):
            for j in range(self.cols):
                x = j * self.cell_w
                y = i * self.cell_h
                painter.drawRect(x, y, self.cell_w, self.cell_h)

        painter.end()

    # =========================================================
    # SIMULATION (GRID LOGIC)
    # =========================================================
    def update_simulation(self):
        i, j = self.robot

        # random movement
        di, dj = random.choice([(1,0), (-1,0), (0,1), (0,-1)])

        ni, nj = i + di, j + dj

        # bounds check
        if 0 <= ni < self.rows and 0 <= nj < self.cols:

            # avoid obstacles
            if self.cells.get((ni, nj)) != 2:

                # mark path
                self.cells[(i, j)] = 3

                self.robot = (ni, nj)

        self.update()

    # =========================================================
    # DRAW (OPTIMIZED)
    # =========================================================
    def paintEvent(self, event):
        painter = QPainter(self)

        # ================= STATIC GRID (FAST BLIT) =================
        painter.drawImage(0, 0, self.grid_image)

        # ================= DYNAMIC CELLS =================
        for (i, j), state in self.cells.items():

            x = j * self.cell_w
            y = i * self.cell_h

            if state == 2:
                color = QColor(0, 0, 0)        # obstacle
            elif state == 3:
                color = QColor(255, 255, 0)    # path
            else:
                continue

            painter.fillRect(x, y, self.cell_w, self.cell_h, color)

        # ================= ROBOT =================
        ri, rj = self.robot
        x = rj * self.cell_w
        y = ri * self.cell_h

        painter.fillRect(
            x, y,
            self.cell_w, self.cell_h,
            QColor(255, 0, 0)
        )
