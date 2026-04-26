import math

class Navigation:
    def __init__(self):
        self.x, self.y = 0.0, 0.0
        self.waypoints = [(1.0, 0.0), (1.0, 1.0), (0.0, 0.0)] # Liste de (x, y)
        self.current_wp_idx = 0
        self.dist_threshold = 0.1 # S'arrêter à 10cm du point

    def update_position(self, delta_ticks_l, delta_ticks_r, current_angle_rad):
        # Distance parcourue par ce cycle
        d_l = delta_ticks_l * 0.0102
        d_r = delta_ticks_r * 0.0102
        d_moy = (d_l + d_r) / 2.0
        
        # Projection trigonométrique
        self.x += d_moy * math.cos(current_angle_rad)
        self.y += d_moy * math.sin(current_angle_rad)

    def get_target_heading(self):
        if self.current_wp_idx >= len(self.waypoints):
            return None, 0
        
        target_x, target_y = self.waypoints[self.current_wp_idx]
        
        dx = target_x - self.x
        dy = target_y - self.y
        
        distance = math.sqrt(dx**2 + dy**2)
        angle_vers_cible = math.degrees(math.atan2(dy, dx))
        
        # Si on est arrivé au point, on passe au suivant
        if distance < self.dist_threshold:
            self.current_wp_idx += 1
            print(f"Waypoint {self.current_wp_idx} atteint !")
            
        return angle_vers_cible, distance
