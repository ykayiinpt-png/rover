import numpy as np

def sign(x):
    if x >= 0:
        return 1
    if x < 0:
        return -1

def dict_equal_fast(d1, d2):
    if len(d1) != len(d2):
        return False
    
    for k, v in d1.items():
        if d2.get(k, object()) != v:
            return False
    
    return True

def clamp(x, min, max):
    if x < min: return min
    if x > max: return max
    return x

def wrap_angle(angle, deg=False):
    """Wind angle  to [-pi, pi]"""
    if deg:
        return (angle + 180) % 360 - 180
    else:
        return (angle + np.pi) % (2 * np.pi) - np.pi