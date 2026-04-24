import numpy as np

class RobotEKF:
    def __init__(self, dt, wheelbase):
        self.dt = dt
        self.L = wheelbase
        
        # 1. State Vector [x, y, theta]
        self.X = np.zeros((3, 1))
        
        # 2. Covariance Matrix P (Uncertainty)
        self.P = np.diag([0.1, 0.1, 0.1])
        
        # 3. Process Noise Q (Trust in the command/odometry)
        # Increase these values if the robot slips or motors are inconsistent
        self.Q = np.diag([0.02, 0.02, 0.05])
        
        # 4. Measurement Noise R (Trust in Sensors)
        # [x_sonar, y_sonar, theta_imu]
        self.R = np.diag([0.1, 0.1, 0.01]) 

    def predict(self, v_cmd, w_cmd):
        """
        PREDICTION STEP
        v_cmd: Linear velocity target from Rover (m/s)
        w_cmd: Angular velocity target from Rover (rad/s)
        """
        theta = self.X[2, 0]

        # --- Update State (Motion Model) ---
        # We predict where the robot SHOULD be based on the command
        self.X[0, 0] += v_cmd * np.cos(theta) * self.dt
        self.X[1, 0] += v_cmd * np.sin(theta) * self.dt
        self.X[2, 0] += w_cmd * self.dt
        
        # Normalize theta between -pi and pi
        self.X[2, 0] = (self.X[2, 0] + np.pi) % (2 * np.pi) - np.pi

        # --- Calculate Jacobian F ---
        # This linearizes the rotation for the covariance update
        F = np.array([
            [1, 0, -v_cmd * np.sin(theta) * self.dt],
            [0, 1,  v_cmd * np.cos(theta) * self.dt],
            [0, 0, 1]
        ])

        # --- Update Covariance ---
        self.P = F @ self.P @ F.T + self.Q

    def update(self, x_sonar, y_sonar, theta_imu):
        """
        UPDATE STEP (Correction)
        x_sonar, y_sonar: Absolute position calculated from walls (can be None)
        theta_imu: Absolute angle from calibrated IMU
        """
        z_list = []
        h_rows = []
        
        # 1. Construct dynamic measurement vector Z and matrix H
        if x_sonar is not None:
            z_list.append(x_sonar)
            h_rows.append([1, 0, 0])
        if y_sonar is not None:
            z_list.append(y_sonar)
            h_rows.append([0, 1, 0])
        
        # We always use the IMU angle for orientation stability
        z_list.append(theta_imu)
        h_rows.append([0, 0, 1])

        Z = np.array(z_list).reshape(-1, 1)
        H = np.array(h_rows)
        
        # Dynamically adjust R size
        current_R = np.eye(len(z_list)) * 0.1
        if len(z_list) == 3: # If we have full X,Y,Theta
            current_R = self.R
        elif len(z_list) == 1: # If only IMU
            current_R = np.array([[self.R[2,2]]])

        # 2. Kalman Gain Calculation
        # Innovation (Error between measurement and prediction)
        y = Z - (H @ self.X)
        
        # Normalize angle error in y
        if len(z_list) > 0:
            y[-1] = (y[-1] + np.pi) % (2 * np.pi) - np.pi

        S = H @ self.P @ H.T + current_R
        K = self.P @ H.T @ np.linalg.inv(S)

        # 3. Final State Update
        self.X = self.X + (K @ y)
        self.P = (np.eye(3) - K @ H) @ self.P

    def get_state(self):
        return self.X[0,0], self.X[1,0], self.X[2,0]