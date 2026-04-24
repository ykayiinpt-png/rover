import logging
import multiprocessing
import time
import numpy as np

from src.raspberry.ekf.imu import ImuEKF
from src.raspberry.hardware.rover import Rover, RoverThread
from src.raspberry.hardware.sensors.imu import IMUSensor
from src.raspberry.hardware.sensors.ultrasound import UltrasoundSensorArray
from src.raspberry.hardware.thread import IMUThread, UltrasoundThread

class ImuEkfController:
    def __init__(self, rover: Rover, sonars_arr_obj: UltrasoundSensorArray, imu: IMUSensor,
                ultrasound_data_sent_queue: multiprocessing.Queue,
                imu_data_send_queue: multiprocessing.Queue,
                odometry_data_sent_queue: multiprocessing.Queue,
                commands_send_queue: multiprocessing.Queue,
                commands_receive_queue: multiprocessing.Queue,
                map_data_send_queue: multiprocessing.Queue):
        self.sonars = sonars_arr_obj
        self.imu = imu
        
        # Fréquences
        self.dt_kalman = 0.05  # 20 Hz (100ms)
        self.last_kalman_time = time.perf_counter()
        
        self.ekf = ImuEKF(dt=self.dt_kalman)
        
        # We assume that we have a square of 8m x 8m to map
        # TODO: later we will handle the over sizing
        self.square_size = 8.0
        
        # Threads
        self.ultra_sound_thread = UltrasoundThread(
            sonars_arr=sonars_arr_obj,
            send_queue=ultrasound_data_sent_queue
        )
        
        self.imu_thread = IMUThread(
            sensor_hw=imu,
            imu_data_send_queue=imu_data_send_queue
        )
        
        self.rover_thread = RoverThread(
            rover=rover,
            odometry_data_sent_queue=odometry_data_sent_queue
        )
        
        self.running = True

    def start_all(self):
        # Calibration obligatoire au démarrage (Robot immobile)
        self.imu.calibrate(samples=100)
        
        # Lancement des threads
        #print("Démarrage de la boucle principale...")
        self.ultra_sound_thread.start()
        logging.info("Robot Controller: Ultrasound thread started")
        self.imu_thread.start()
        logging.info("Robot Controller: Imu thread has started")
        self.rover_thread.start()
        logging.info("Robot Controller: Rover Thread thread started")
        #print("Robot prêt et EKF initialisé.")
        
        #self.rover_thread.rover.move(0.5, 0)

    def run(self):
        #print("[CRITICAL] Don't move the robot for a while")
        self.start_all()
        #print("[INFO] You can move the robot")
        
        last_time = time.perf_counter()

        try:
            while self.running:
                now = time.perf_counter()
                loop_dt = now - last_time

                if loop_dt >= self.dt_kalman:
                    # --- A. ACQUISITION DES DONNÉES FILTRÉES ---
                    imu_data = self.imu_thread.get_latest_data()
                    accel_x, gyro_z, yaw_imu  =  imu_data
                    #print("Gyro data", imu_data)

                    # --- B. ÉTAPE DE PRÉDICTION (EKF) ---
                    # On utilise l'IMU pour prédire le mouvement
                    self.ekf.predict(accel_x, gyro_z)

                    # --- C. ÉTAPE DE CORRECTION (EKF) ---
                    # On récupère les ultrasons (Thread Sonar)
                    distances = self.ultra_sound_thread.get_last_scan_data()
                    #print(distances)
                    
                    # Calcul de la position observée via les murs (8x8m)
                    x_s, y_s = self.calculate_sonar_pos(distances, yaw_imu)
                    
                    # Mise à jour du filtre
                    self.ekf.update(x_s, y_s, yaw_imu)

                    # --- D. GESTION DE LA DÉRIVE (ZUPT) ---
                    # Si on ne demande pas de mouvement, on force la vitesse à 0
                    if self.rover_thread.rover.target_linear == 0:
                        self.ekf.force_stop()

                    # --- E. LOGGING / CARTOGRAPHIE ---
                    x, y, theta = self.ekf.get_position()
                    #print(f"Pos: {x:.2f}, {y:.2f} | Angle: {theta:.2f}")

                    last_time = now

                # Petite pause pour laisser le CPU respirer
                time.sleep(0.01)

        except KeyboardInterrupt:
            self.stop()

    def calculate_sonar_pos(self, dists, theta):
        #print("Distances: ", dists)
        x_obs_list = []
        y_obs_list = []

        # Définition des angles de chaque capteur par rapport au corps du robot
        # Avant: 0, Gauche: +90°, Arrière: 180°, Droite: -90°
        sensors = [
            ('u_f',   0),
            ('u_l',  np.pi/2),
            ('u_b', np.pi),
            ('u_r', -np.pi/2)
        ]

        for key, offset in sensors:
            if dists.get("key") is None:
                continue
            
            d = dists[key]
            if d > 3.0 or d < 0.02: continue # Ignorer si trop loin ou erreur
            
            # Angle absolu du faisceau dans la pièce
            # We say normalizing angle
            abs_angle = (theta + offset + np.pi) % (2 * np.pi) - np.pi
            
            # Projection de la distance sur les axes X et Y
            # C'est ici que la trigonométrie corrige la "diagonale"
            dist_x = d * np.cos(abs_angle)
            dist_y = d * np.sin(abs_angle)

            # 1. Quel mur ce capteur touche-t-il ?
            # Si le faisceau pointe vers la droite (Est)
            if np.cos(abs_angle) > 0.8: # Environ +/- 36° autour de l'axe X
                x_obs_list.append(self.square_size - dist_x)
            # Si le faisceau pointe vers la gauche (Ouest)
            elif np.cos(abs_angle) < -0.8:
                x_obs_list.append(0.0 - dist_x) # dist_x sera négatif, donc 0 - (-val) = +val

            # Si le faisceau pointe vers le haut (Nord)
            if np.sin(abs_angle) > 0.8:
                y_obs_list.append(self.square_size - dist_y)
            # Si le faisceau pointe vers le bas (Sud)
            elif np.sin(abs_angle) < -0.8:
                y_obs_list.append(0.0 - dist_y)

        # Faire la moyenne des observations pour X et Y
        x_s = sum(x_obs_list) / len(x_obs_list) if len(x_obs_list) > 0 else None
        y_s = sum(y_obs_list) / len(y_obs_list) if len(y_obs_list) > 0 else None

        return x_s, y_s

        
    def stop(self):
        self.running = False
        logging.info("[ImuEkfController] Set stop event")
        
        self.ultra_sound_thread.shutdown()
        self.ultra_sound_thread.join()
        
        self.imu_thread.shutdown()
        self.imu_thread.join()
        
        self.rover_thread.shutdown()
        self.rover_thread.join()
        
        #print("Système arrêté proprement.")
