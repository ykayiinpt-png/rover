import sys
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtWidgets import QApplication

# -------------------------
# CONFIG
# -------------------------
CSV_FILE = ".\\notebooks\\inputs\\straightlineright.csv"

# -------------------------
# LOAD DATA
# -------------------------
df = pd.read_csv(CSV_FILE)

# On suppose que les colonnes sont :
# Command_x, Command_y, Target_x, Target_y

t_cmd = df["Command_x"].values
t_tgt = df["Target_x"].values

cmd_y = df["Command_y"].values
tgt_y = df["Target_y"].values

# Normalisation du temps (plus lisible)
t0 = min(t_cmd[0], t_tgt[0])
t_cmd = t_cmd - t0
t_tgt = t_tgt - t0

# -------------------------
# APP PYQTGRAPH
# -------------------------
app = QApplication(sys.argv)
app.styleHints().setColorScheme(Qt.ColorScheme.Light)

styles = {"color": "black"}

win = pg.GraphicsLayoutWidget(show=True, title="Asservissement Roue Droite")
win.resize(1000, 600)
win.setBackground(None)

# Style scientifique léger
pg.setConfigOptions(antialias=True)

# -------------------------
# PLOT 1 : Command
# -------------------------
# p1 = win.addPlot(title="Command Y vs Time")
# p1.setLabel("left", "Command Y")
# p1.setLabel("bottom", "Time (s)")
# p1.showGrid(x=True, y=True, alpha=0.3)

# p1.plot(t_cmd, cmd_y, pen=pg.mkPen("b", width=2), name="Command Y")

# win.nextRow()

# # -------------------------
# # PLOT 2 : Target
# # -------------------------
# p2 = win.addPlot(title="Target Y vs Time")
# p2.setLabel("left", "Target Y")
# p2.setLabel("bottom", "Time (s)")
# p2.showGrid(x=True, y=True, alpha=0.3)

# p2.plot(t_tgt, tgt_y, pen=pg.mkPen("r", width=2), name="Target Y")

# # -------------------------
# # BONUS : overlay comparaison
# # -------------------------
# win.nextRow()

p3 = win.addPlot(title="Comparison")
p3.setLabel("left", "Vitesse (RPM°)")
p3.setLabel("bottom", "Temps (s)")
p3.getAxis("left").setTextPen("k")
p3.getAxis("bottom").setTextPen("k")
#p3.setBackground("transparent")
p3.addLegend()
p3.showGrid(x=True, y=True, alpha=0.3)
p3.plot(t_cmd, cmd_y, pen=pg.mkPen("b", width=2), name="Command", **styles)
p3.plot(t_tgt, tgt_y, pen=pg.mkPen("r", width=2), name="Target", **styles)

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    sys.exit(app.exec())
