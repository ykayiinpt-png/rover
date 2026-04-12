import asyncio
import datetime
import json
import logging
import time
import random

from aiomqtt import Topic

from src.component.thread_mqtt import ThreadMqttComponent
from src.component.thread_ws import ThreadWsComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.client import WebSocketClient
from src.ws.mqtt_client import MqttClient


class FakeSensorDatAcquisitionMqtt(RThread):
    def __init__(self):
        super().__init__()
        
        self.counter = 0
        
    def run(self):
        while not self.stop_event.is_set():
            data = {
                "topic": "testtopic/test",
                "payload": {
                    "mission_id": 1, 
                    "timestamp": int(datetime.datetime.timestamp(datetime.datetime.now())),
                    "payload": [
                        {"u_sund_front": self.counter}
                    ]
                }
            }
            
            #for i in range(20):
            #    data['payload'].append({"u_sund_front": self.counter + 1})
                
            self.counter +=  ((-1) ** random.randint(0, 5)) * random.randint(0, 10)
            
            self.queue_bridge.push_from_thread(data)
            
            logging.info("Data sent to sync queue")
            
            time.sleep(10)
        
        logging.info("Thread stop event up")
            
class FakeSensorMqtt(MqttClient):
    
    def __init__(self, uri, port, topics: list[Topic], async_event_loop):
        super().__init__(uri, port, topics, async_event_loop)
            


class FakeSensorMqttWrapper:
    
    def __init__(self, uri, port, async_event_loop):        
        self.component = ThreadMqttComponent(
            FakeSensorDatAcquisitionMqtt(),
            FakeSensorMqtt(
                uri,
                port,
                topics=["testtopic/test"],
                async_event_loop=async_event_loop),
            ThreadCoroutineBridge(async_event_loop),
            async_event_loop=async_event_loop
        )
        
    async def run(self):
        await self.component.start()
        
    async def clean(self):
        await self.component.stop()