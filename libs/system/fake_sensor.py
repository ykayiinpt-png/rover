import datetime
import json
import logging
import time
import random

from libs.component.thread_ws import ThreadWsComponent
from libs.threads import RThread
from libs.ws.client import WebSocketClient


class FakeSensorDatAcquisition(RThread):
    def __init__(self):
        super().__init__()
        
        self.counter = 0
        
    def run(self):
        while not self.stop_event.is_set():
            data = {
                "mission_id": 1, 
                "timestamp": int(datetime.datetime.timestamp(datetime.datetime.now())),
                "payload": [
                    {"u_sund_front": self.counter}
                ]
            }
            
            for i in range(20):
                data['payload'].append({"u_sund_front": self.counter + 1})
                
            self.counter +=  ((-1) ** random.randint(0, 5)) * random.randint(0, 10)
            
            self.sync_q.put(json.dumps(data))
            
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