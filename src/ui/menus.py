from PyQt6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QVBoxLayout
from PyQt6.QtCore import Qt

class AccquisitionMenuSensorsParameters(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setWindowTitle("Acquisition - Sensors Parameters")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        #self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.setFixedWidth(500)
        
        main_grid = QGridLayout(self)
        
        # === Ultrasonic ===
        ultra_group = QGroupBox("Ultrasonic")
        ultra_layout = QVBoxLayout()

        self.ultra_front = QCheckBox("Front")
        self.ultra_back = QCheckBox("Back")
        self.ultra_left = QCheckBox("Left")
        self.ultra_right = QCheckBox("Right")

        for cb in [self.ultra_front, self.ultra_back, self.ultra_left, self.ultra_right]:
            ultra_layout.addWidget(cb)

        ultra_group.setLayout(ultra_layout)

        # === Accelerometer ===
        accel_group = QGroupBox("Accelerometer")
        accel_layout = QVBoxLayout()

        self.accel_x = QCheckBox("X")
        self.accel_y = QCheckBox("Y")
        self.accel_z = QCheckBox("Z")

        for cb in [self.accel_x, self.accel_y, self.accel_z]:
            accel_layout.addWidget(cb)

        accel_group.setLayout(accel_layout)

        # === Rotation ===
        gyro_group = QGroupBox("Rotation")
        gyro_layout = QVBoxLayout()

        self.rot_x = QCheckBox("X")
        self.rot_y = QCheckBox("Y")
        self.rot_z = QCheckBox("Z")

        for cb in [self.rot_x, self.rot_y, self.rot_z]:
            gyro_layout.addWidget(cb)

        gyro_group.setLayout(gyro_layout)

        # === Data Options ===
        data_group = QGroupBox("Data")
        data_layout = QVBoxLayout()

        self.raw_data = QCheckBox("Raw")
        self.filtered_data = QCheckBox("Filtered")

        data_layout.addWidget(self.raw_data)
        data_layout.addWidget(self.filtered_data)

        data_group.setLayout(data_layout)

        # === Buttons ===
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # === Place everything in MAIN GRID ===
        main_grid.addWidget(ultra_group, 0, 0)
        main_grid.addWidget(accel_group, 0, 1)
        main_grid.addWidget(gyro_group, 1, 0)
        main_grid.addWidget(data_group, 1, 1)

        # Buttons span both columns
        main_grid.addWidget(buttons, 2, 0, 1, 2)
        
    def get_selected_options(self):
        return {
            "ultrasonic": {
                "front": self.ultra_front.isChecked(),
                "back": self.ultra_back.isChecked(),
                "left": self.ultra_left.isChecked(),
                "right": self.ultra_right.isChecked(),
            },
            "accelerometer": {
                "x": self.accel_x.isChecked(),
                "y": self.accel_y.isChecked(),
                "z": self.accel_z.isChecked(),
            },
            "rotation": {
                "x": self.rot_x.isChecked(),
                "y": self.rot_y.isChecked(),
                "z": self.rot_z.isChecked(),
            },
            "data": {
                "raw": self.raw_data.isChecked(),
                "filtered": self.filtered_data.isChecked(),
            }
        }
        
        