
def sign(x):
    return (x > 0) - (x < 0)

def dict_equal_fast(d1, d2):
    if len(d1) != len(d2):
        return False
    
    for k, v in d1.items():
        if d2.get(k, object()) != v:
            return False
    
    return True