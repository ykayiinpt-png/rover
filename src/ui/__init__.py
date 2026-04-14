from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QMainWindow, QPushButton, QWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("My App")
        button = QPushButton("Press Me!")
        button.setCheckable(True)
        button.clicked.connect(self.handle_btn_clicked)
        
        self.setFixedSize(QSize(400, 300))
        
        self.setCentralWidget(button)
        
    def handle_btn_clicked(self):
        print("Clicked")
        
    def closeEvent(self, a0):
        """
        We stop Process here
        """
        
        return super().closeEvent(a0)
        