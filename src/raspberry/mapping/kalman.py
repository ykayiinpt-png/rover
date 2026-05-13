import numpy as np

from src.core.utils import wrap_angle


class KalmanMapping:
    """
    Obstacle Mapping with the kalman filter approach
    """
    
    def __init__(self, dt):
        self.dt = dt
        self.X = np.zeros((3, 1)) # [x, y, theta]
        self.P = np.diag([0.1, 0.1, 0.1])
        self.Q = np.diag([0.02, 0.02, 0.01]) # Bruit process
        self.R = np.diag([0.01]) # Confiance absolue en l'angle IMU

    def predict(self, v, w, dt):
        theta = self.X[2, 0]
        
        self.X[0, 0] += v * np.cos(theta) * dt
        self.X[1, 0] += v * np.sin(theta) * dt
        self.X[2, 0] += w * dt
        self.X[2, 0] = wrap_angle(self.X[2, 0], deg=False)

        # Jacobienne F
        F = np.array([
            [1, 0, -v * np.sin(theta) * dt],
            [0, 1,  v * np.cos(theta) * dt],
            [0, 0, 1]
        ])
        self.P = F @ self.P @ F.T + self.Q

    def update_yaw(self, yaw_imu):
        # Correction uniquement sur l'angle (stabilité cap)
        Z = np.array([[yaw_imu]])
        H = np.array([[0, 0, 1]])
        
        y = Z - (H @ self.X)
        y[0, 0] = wrap_angle(y[0, 0], deg=False)
        
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)
        
        self.X = self.X + (K @ y)
        self.P = (np.eye(3) - K @ H) @ self.P

    def get_state(self):
        return self.X[0,0], self.X[1,0], self.X[2,0]
