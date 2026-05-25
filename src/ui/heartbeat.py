import asyncio
import logging
import multiprocessing
import time

from src.core.shared import MemorySharedDict
from src.raspberry.component.thread_mqtt import ThreadMqttComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.mqtt_client import MqttClient


class Pi4HeartBeatAckMqtt(RThread):
    """
    Heartbeat Monitoring
    """
    
    def __init__(self, ui_state: MemorySharedDict):
        super().__init__()
        self.ui_state = ui_state
        
    def run(self):
        last_heartbeat = time.perf_counter()
        
        while not self.stop_event.is_set():
            now = time.perf_counter()
            
            if not self.queue_bridge.q_sync.empty():
                self.queue_bridge.q_sync.get()
                
                self.ui_state["alive"] = True
                last_heartbeat = now
                
            if now - last_heartbeat > 3:
                self.ui_state["alive"] = False
                
            self.queue_bridge.push_from_thread({
                "topic": "slam/heartbeat/remote",
                "payload": {"from": "Station"}
            })
            
            time.sleep(1)
        
        logging.info("[Pi4HeartBeatAckMqtt] Thread stop event up")
        
    def stop(self):
        logging.info("[Pi4HeartBeatAckMqtt] Requested stop...")
        self.stop_event.set()



class Pi4HeartBeatAckProcess(multiprocessing.Process):
    """
    Commands exchange with an autonous system, a raspberry pi
    """
    
    def __init__(self, host: str, port: int, 
                 ui_state: MemorySharedDict,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.stop_event = None
        
        self.host = host
        self.port = port
        self.mqtt_client = None
        self.ui_state = ui_state
        
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[Pi4HeartBeatAckProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[Pi4HeartBeatAckProcess] Exception occured")
            raise e
        finally:
            pass
            #self.data_queue.close()
            
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        
        self.mqtt_client = MqttClient(
            uri=self.host, port=self.port,
            topics=[
                # Heatbeats from the rover local
                "slam/heartbeat/local"
            ],
            async_event_loop=loop
        )
        
        self.component = ThreadMqttComponent(
            Pi4HeartBeatAckMqtt(ui_state=self.ui_state),
            self.mqtt_client,
            ThreadCoroutineBridge(loop),
            async_event_loop=loop
        )
        
        try:
            await self.component.start()
            
            # We wait until finisshed
            await self.stop_event.wait()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            logging.warning("[Pi4HeartBeatAckProcess] CancelledError fired")
            pass
        finally:
            logging.info("[Pi4HeartBeatAckProcess] Closing async process")
            await self.stop()
        
            logging.info("[Pi4HeartBeatAckProcess] Finally closed")
            
    async def stop(self):
        self.stop_event.set()
        
        await self.component.stop()
        
        if self.mqtt_client:
            r = await asyncio.shield(self.mqtt_client.close())
            if isinstance(r, Exception):
                logging.exception(r)
            
        
        