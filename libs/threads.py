import threading

class RThread(threading.Thread):
    """
    Augmented thread for looping task.
    
    It adds a stop_event threading.Event that will be used incase of 
    an infinite loop
    """
    
    def __init__(self,):
        threading.Thread.__init__(self)
        
        self.stop_event = threading.Event()
        
        # Queue for communication
        self.sync_q = None