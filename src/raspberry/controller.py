import time

from src.raspberry.hardware.sensors.imu import IMUSensor
from src.raspberry.hardware.sensors.ultrasound import UltrasoundSensorArray

class RobotController:
    def __init__(self, sonar_array: UltrasoundSensorArray, imu: IMUSensor, odometry):
        self.sonars = sonar_array
        self.imu = imu
        self.odometry = odometry
        
        # Fréquences
        self.dt_kalman = 0.1  # 10 Hz (100ms)
        self.last_kalman_time = time.perf_counter()
        
        self.running = True

    def run(self):
        print("Démarrage de la boucle principale...")
        try:
            while self.running:
                now = time.perf_counter()
                
                # --- ÉTAPE 1 : PID & Encodeurs (Haute Fréquence virtuelle) ---
                # Dans un vrai système, le PID serait dans un thread séparé.
                # Ici, on récupère les données de mouvement.
                #movement = self.odometry.get_movement()

                # --- ÉTAPE 2 : IMU (Mise à jour constante) ---
                self.imu.update()
                
                # --- ÉTAPE 3 : FILTRE DE KALMAN (Toutes les 100ms) ---
                if now - self.last_kalman_time >= self.dt_kalman:
                    #self._execute_kalman_cycle(movement)
                    self.last_kalman_time = now
                    
                    self.sonars.scan_sequence() # TODO: Will be removed

                # Petite pause pour ne pas saturer le CPU à 100%
                time.sleep(0.01) 

        except KeyboardInterrupt:
            self.stop()

    def _execute_kalman_cycle(self, movement):
        """Phase de calcul intensive"""
        # 1. PRÉDICTION (Basée sur l'odométrie et l'IMU)
        dist = movement['distance']
        heading = self.imu.get_data()['gyro']['z']
        print(f"[Kalman] Prédiction : Déplacement de {dist:.2f}mm")

        # 2. CAPTURE ULTRASONS (Perception)
        # Rappel : scan_sequence prend ~100ms car il attend les échos
        distances = self.sonars.scan_sequence()
        
        # 3. CORRECTION & DATA ASSOCIATION
        # C'est ici qu'on mettra à jour la carte avec 'distances'
        print(f"[Kalman] Correction : Obstacles à {distances}")

    def stop(self):
        self.running = False
        self.sonars.shutdown()
        
        if self.odometry:
            self.odometry.stop()
        
        self.imu.stop()
        print("Système arrêté proprement.")