import logging
import time

from libs.component.thread_ws import ThreadWsComponent
from libs.threads import RThread
from libs.ws.client import WebSocketClient


class FakeSensorDatAcquisition(RThread):
    def __init__(self):
        super().__init__()
        
        self.counter = 0
        
    def run(self):
        while not self.stop_event.is_set():
            data = { "counter": self.counter }
            self.counter += 1
            
            self.sync_q.put(data.copy())
            
            logging.info("Data sent to sync queue")
            
            time.sleep(2)
        
        logging.info("Thread stop event up")
            
class FakeSensorWs(WebSocketClient):
    
    def __init__(self, uri):
        super().__init__(uri)
            


class FakeSensorWrapper:
    
    def __init__(self, uri):
        
        self.component = ThreadWsComponent(
            FakeSensorDatAcquisition(),
            FakeSensorWs(uri)
        )