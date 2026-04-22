import numpy as np
import time

class ImuEKF:
    def __init__(self, dt):
        self.dt = dt
        
        # 1. État : [x, y, v, theta] 
        # (Position x, y, Vitesse linéaire v, Angle theta)
        self.X = np.zeros((4, 1))
        
        # 2. Matrice de Covariance P (Incertitude)
        # On commence avec une incertitude modérée
        self.P = np.diag([0.1, 0.1, 0.1, 0.1])
        
        # 3. Bruit de Processus Q (Confiance dans l'IMU)
        # On augmente la valeur pour 'v' car l'accéléromètre dérive
        self.Q = np.diag([0.001, 0.001, 0.05, 0.002])
        
        # 4. Bruit de Mesure R (Confiance dans les Ultrasons/IMU)
        # [x_sonar, y_sonar, theta_imu]
        self.R_default = np.diag([0.1, 0.1, 0.01])

    def predict(self, accel_x, gyro_z):
        """
        Phase de prédiction (Modèle physique)
        accel_x : accélération filtrée (m/s^2)
        gyro_z : vitesse de rotation (rad/s)
        """
        # Extraction des variables d'état
        x, y, v, theta = self.X.flatten()

        # --- Mise à jour de l'état (Équations de mouvement) ---
        new_v = v + (accel_x * self.dt)
        # On évite les vitesses négatives si le robot ne recule pas
        new_v = max(0, new_v) 
        
        new_x = x + (v * np.cos(theta) * self.dt)
        new_y = y + (v * np.sin(theta) * self.dt)
        new_theta = (theta + (gyro_z * self.dt) + np.pi) % (2 * np.pi) - np.pi

        self.X = np.array([[new_x], [new_y], [new_v], [new_theta]])

        # --- Calcul du Jacobien F (Linéarisation de l'état) ---
        F = np.array([
            [1, 0, np.cos(theta)*self.dt, -v*np.sin(theta)*self.dt],
            [0, 1, np.sin(theta)*self.dt,  v*np.cos(theta)*self.dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])

        # --- Mise à jour de la covariance ---
        self.P = F @ self.P @ F.T + self.Q

    def update(self, x_s, y_s, theta_imu):
        """
        Phase de correction (Ultrasons + Angle IMU)
        x_s, y_s : position calculée via murs (peut être None)
        """
        # Préparation de la mesure Z et de la matrice H
        z_list = []
        h_list = []
        r_list = []

        # Si l'ultrason donne une position X fiable
        if x_s is not None:
            z_list.append(x_s)
            h_list.append([1, 0, 0, 0])
            r_list.append(self.R_default[0,0])

        # Si l'ultrason donne une position Y fiable
        if y_s is not None:
            z_list.append(y_s)
            h_list.append([0, 1, 0, 0])
            r_list.append(self.R_default[1,1])

        # On ajoute toujours l'angle IMU (très fiable)
        z_list.append(theta_imu)
        h_list.append([0, 0, 0, 1])
        r_list.append(self.R_default[2,2])

        # Conversion en matrices NumPy
        Z = np.array(z_list).reshape(-1, 1)
        H = np.array(h_list)
        R = np.diag(r_list)

        # --- Calcul du Gain de Kalman ---
        # y = Z - H*X (Innovation)
        y = Z - (H @ self.X)
        
        # Normalisation de l'erreur d'angle (le dernier élément de y)
        y[-1] = (y[-1] + np.pi) % (2 * np.pi) - np.pi

        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)

        # --- Mise à jour finale ---
        self.X = self.X + (K @ y)
        self.P = (np.eye(4) - K @ H) @ self.P

    def force_stop(self):
        """Réinitialise la vitesse à zéro (ZUPT) pour tuer la dérive"""
        self.X[2] = 0.0
        self.P[2,2] = 0.001 # On devient très sûr que la vitesse est nulle

    def get_position(self):
        return self.X[0,0], self.X[1,0], self.X[3,0]
