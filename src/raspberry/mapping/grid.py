from datetime import datetime, timezone
import logging

import numpy as np

class OccupancyMap:
    def __init__(self, width_m, height_m, resolution_x=0.1, resolution_y=0.1,
                 cone_angle=np.deg2rad(15), # 15° by default
                 num_rays=10,
                 log_odds_free_prob=-0.4, log_odds_occup_prob=0.85,
                 save_grid_to_file=True):
        self.res_x = resolution_x # 0.1m = 10cm par case
        self.res_y = resolution_y
        self.l_occ = log_odds_occup_prob
        self.l_free = log_odds_free_prob
        self.width = int(width_m / resolution_x)
        self.height = int(height_m / resolution_y)
        
        self.rx = 0
        self.ry = 0
        
        # Garder dimensions physiques
        self.width_m = width_m
        self.height_m = height_m
        
        # Ultrasound parameters
        self.cone_angle = cone_angle #np.deg2rad(15)   # 15°
        self.num_rays = num_rays  
        self.cone_rays_angles = np.linspace(-self.cone_angle/2, self.cone_angle/2, self.num_rays)
        
        # Initialisation : 0.5 = inconnu, >0.5 = obstacle, <0.5 = libre
        self.grid = np.full((self.height, self.width), 0.5)
        self.logodds = np.zeros((self.height, self.width))
        
        self.last_updated_cells = dict()
        
        self.save_grid_to_file = save_grid_to_file

    def mark_obstacle(self, rx, ry, rtheta, dist, sensor_offset):
        """
        rx, ry, rtheta : Position filtrée par l'EKF
        dist : Distance mesurée par l'ultrason
        sensor_offset dict[str, float] : Angle du capteur
        """
        
        # On récupère les indices du robot lui-même
        self.rx = int((rx + self.width_m / 2) / self.res_y)
        self.ry = int((ry + self.height_m / 2) / self.res_x)
        
        for delta in self.cone_rays_angles:
            # 1. Calcul de l'angle absolu du faisceau dans le monde
            beam_angle = rtheta + sensor_offset + delta
            
            # 2. Coordonnées (x, y) de l'obstacle dans le monde (en mètres)
            obj_x = rx + dist * np.cos(beam_angle)
            obj_y = ry + dist * np.sin(beam_angle)
            
            # 3. Conversion en indices de matrice (pixels)
            #grid_x = int(obj_x / self.res_y)
            #grid_y = int(obj_y / self.res_x)
            
            grid_x = int((obj_x + self.width_m / 2) / self.res_x)
            grid_y = int((obj_y + self.height_m / 2) / self.res_y)
            
            weight = 1.0 - abs(delta) / (self.cone_angle / 2)
            # weight = np.exp(-(delta**2)/(2*sigma**2))
            
            #print("\n\n\n\n")
            #print("Grid Values: ", grid_y, grid_x, "rtheta:", rtheta, "offset:", sensor_offset, "tobot:", (rx, ry))
            # 4. Mise à jour de la grille (Probabiliste)
            if 0 <= grid_x < self.width and 0 <= grid_y < self.height:             
                self.free_path_and_mark_obstacle(self.rx, self.ry, grid_x, grid_y, weight)
            else:
                pass
                #print("Out of bound: ", "max", "w:", self.width, "h:", self.height)
                #print("\n\n\n")
            
    def get_cells_updated_and_reset(self):
        """
        Return a copy of the cells most recently updated by
        `mark_obstacle()`, then clear the internal tracking list.

        Returns:
            list: A copy of the updated cells. Item in they has the format (x, y, value)
        """
        cp = [[x, y, v] for (x, y), v in self.last_updated_cells.items()]
        self.last_updated_cells.clear()
        
        src_h, src_w = self.logodds.shape
        target_rows, target_cols = src_h, src_w
        
        return {
            "dim": [target_rows, target_cols],
            "cells": cp
        }
        
            
    # def free_path(self, x0, y0, x1, y1):
    #     """ Marque les cases comme libres entre le robot (x0,y0) et l'obstacle (x1,y1) """
    #     # On peut utiliser un simple échantillonnage entre les deux points
    #     steps = max(abs(x1 - x0), abs(y1 - y0))
    #     if steps == 0:
    #         return
        
    #     for i in range(steps):
    #         t = i / steps
    #         curr_x = int(x0 + t * (x1 - x0))
    #         curr_y = int(y0 + t * (y1 - y0))
            
    #         # On réduit la probabilité d'obstacle sur le chemin
    #         if 0 <= curr_x < self.width and 0 <= curr_y < self.height:
    #             # 0.0 = complètement libre
    #             self.grid[curr_y, curr_x] = max(0.0, self.grid[curr_y, curr_x] - 0.1)
                
    # def free_path(self, x0, y0, x1, y1):
    #     """ Marque les cases comme libres entre le robot (x0,y0) et l'obstacle (x1,y1) """
    #     # On peut utiliser un simple échantillonnage entre les deux points
    #     cells = self.bresenham(x0, y0, x1, y1)

    #     # on enlève la dernière cellule (obstacle)
    #     for x, y in cells[:-1]:

    #         if 0 <= x < self.width and 0 <= y < self.height:

    #             self.grid[y, x] = max(
    #                 0.0,
    #                 self.grid[y, x] - 0.1
    #             )
                
    
    def free_path_and_mark_obstacle(self, x0, y0, x1, y1, obstacle_weight=1.0):
        cells = self.bresenham(x0, y0, x1, y1)

        if len(cells) == 0:
            return

        # 1. LIBRE : tous les points sauf le dernier
        for x, y in cells[:-1]:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.logodds[y, x] += self.l_free

                # clamp (évite explosion numérique)
                self.logodds[y, x] = np.clip(self.logodds[y, x], -5, 5)
                
                self.last_updated_cells[(x, y)] = self.logodds[y, x]

        # 2. OBSTACLE : dernier point
        x, y = cells[-1]

        if 0 <= x < self.width and 0 <= y < self.height:
            self.logodds[y, x] += self.l_occ * obstacle_weight
            self.logodds[y, x] = np.clip(self.logodds[y, x], -5, 5)
            
            self.last_updated_cells[(x, y)] = self.logodds[y, x]
                
    def bresenham(self, x0, y0, x1, y1):
        """Retourne les cellules d'une ligne discrète (Bresenham)"""

        cells = []

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)

        x, y = x0, y0

        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1

        if dx > dy:
            err = dx / 2.0
            while x != x1:
                cells.append((x, y))
                err -= dy
                if err < 0:
                    y += sy
                    err += dx
                x += sx
        else:
            err = dy / 2.0
            while y != y1:
                cells.append((x, y))
                err -= dx
                if err < 0:
                    x += sx
                    err += dy
                y += sy

        cells.append((x1, y1))
        return cells

    
    def grid_to_slot_format(self):
        """
        Convert a 2D NumPy array to the 'slot_update_grid' format.

        Parameters:
        - grid: np.ndarray of shape (h, w) with float values [0,1]
        - target_rows, target_cols: optional rescale target dimensions
        """
        src_h, src_w = self.logodds.shape
        target_rows, target_cols = src_h, src_w

        cells = []
        for y in range(target_rows):
            for x in range(target_cols):
                prob = float(self.logodds[y, x])
                cells.append([x, y, prob])

        return {
            "dim": [target_rows, target_cols],
            "cells": cells
        }
        
    def stop(self):
        if self.save_grid_to_file:
            try:
                np.save(f'occupancy_grid_{datetime.now(timezone.utc).timestamp()}.npy', self.logodds)
            except Exception:
                print("Exception in grid....")
                logging.exception("[OccupancyGrid]")
