from datetime import datetime, timezone

import numpy as np

class OccupancyMap:
    def __init__(self, width_m, height_m, resolution=0.1, save_grid_to_file=True):
        self.res = resolution # 0.1m = 10cm par case
        self.width = int(width_m / resolution)
        self.height = int(height_m / resolution)
        
        # Initialisation : 0.5 = inconnu, >0.5 = obstacle, <0.5 = libre
        self.grid = np.full((self.width, self.height), 0.5)
        self.save_grid_to_file = save_grid_to_file

    def mark_obstacle(self, rx, ry, rtheta, dist, sensor_offset):
        """
        rx, ry, rtheta : Position filtrée par l'EKF
        dist : Distance mesurée par l'ultrason
        sensor_offset dict[str, float] : Angle du capteur
        """
        # 1. Calcul de l'angle absolu du faisceau dans le monde
        beam_angle = rtheta + sensor_offset
        
        # 2. Coordonnées (x, y) de l'obstacle dans le monde (en mètres)
        obj_x = rx + dist * np.cos(beam_angle)
        obj_y = ry + dist * np.sin(beam_angle)
        
        # 3. Conversion en indices de matrice (pixels)
        grid_x = int(obj_x / self.res)
        grid_y = int(obj_y / self.res)
        
        grid_x = int((obj_x + self.width / 2) / self.res)
        grid_y = int((obj_y + self.height / 2) / self.res)
        
        # 4. Mise à jour de la grille (Probabiliste)
        if 0 <= grid_x < self.width and 0 <= grid_y < self.height:
            # On augmente la probabilité d'obstacle (max 1.0)
            self.grid[grid_x, grid_y] = min(1.0, self.grid[grid_x, grid_y] + 0.2)
            
            # TODO: à faire
            # OPTIONNEL: On peut aussi "libérer" l'espace entre le robot et l'obstacle
            # en traçant une ligne de cases "libres" (Bresenham's algorithm)
            # --- LIBÉRER L'ESPACE (Bresenham light) ---
            # On récupère les indices du robot lui-même
            start_x = int((rx + self.width_m / 2) / self.res)
            start_y = int((ry + self.height_m / 2) / self.res)
            self.free_path(start_x, start_y, grid_x, grid_y)
            
    def free_path(self, x0, y0, x1, y1):
        """ Marque les cases comme libres entre le robot (x0,y0) et l'obstacle (x1,y1) """
        # On peut utiliser un simple échantillonnage entre les deux points
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(steps):
            t = i / steps
            curr_x = int(x0 + t * (x1 - x0))
            curr_y = int(y0 + t * (y1 - y0))
            
            # On réduit la probabilité d'obstacle sur le chemin
            if 0 <= curr_x < self.width and 0 <= curr_y < self.height:
                # 0.0 = complètement libre
                self.grid[curr_x, curr_y] = max(0.0, self.grid[curr_x, curr_y] - 0.1)

            
    def stop(self):
        if self.save_grid_to_file:
            try:
                np.save(f'occupancy_grid_{datetime.now(timezone.utc).timestamp()}.npy', self.grid)
            except Exception:
                pass
