import asyncio
import logging
import multiprocessing
import time

from src.raspberry.component.thread_mqtt import ThreadMqttComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.mqtt_client import MqttClient


class RaspberryCommandsAckMqtt(RThread):
    """
    Commands exchanges between the current app and the rapberry
    
    It sends commands to the raspberry pi and receives also commands
    from the raspberry pi. Command received are actions triggered by the
    raspberry itself
    """
    
    def __init__(self, send_queue: multiprocessing.Queue, receive_queue: multiprocessing.Queue):
        super().__init__()
        
        self.send_queue = send_queue
        self.receive_queue = receive_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Check if we have data from the remote server
            if not self.queue_bridge.q_sync.empty():
                payload = self.queue_bridge.q_sync.get_nowait()
                print("Data from remote server")
                print(payload)
                print(type(payload))
                
                self.receive_queue.put(payload)
            
            # We do have somthing to send
            if not self.send_queue.empty():
                data = self.send_queue.get()
                self.queue_bridge.push_from_thread({
                    "topic": data.get("topic", "all"),
                    "payload": data.get("payload")
                })
            
            time.sleep(0.01)
        
        logging.info("[RaspberryCommandsAckMqtt] Thread stop event up")
        
    def stop(self):
        logging.info("[RaspberryCommandsAckMqtt] Requested stop...")
        self.stop_event.set()



class RaspberryCommandsAckProcess(multiprocessing.Process):
    """
    Commands exchange with an autonous system, a raspberry pi
    """
    
    def __init__(self, host: str, port: int, 
                 send_queue: multiprocessing.Queue, receive_queue: multiprocessing.Queue,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.stop_event = None
        
        self.host = host
        self.port = port
        self.mqtt_client = None
        
        
        self.send_queue = send_queue
        self.receive_queue = receive_queue
        
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[RaspberryCommandsAckProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[RaspberryCommandsAckProcess] Exception occured")
            raise e
        finally:
            self.data_queue.close()
            
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        
        self.mqtt_client = MqttClient(
            uri=self.host, port=self.port,
            # Only topics for data reception
            # Read command exécute for decision taking
            # the rover system itself
            topics=["slam/rover/commands/local"],
            async_event_loop=loop
        )
        
        self.component = ThreadMqttComponent(
            RaspberryCommandsAckMqtt(
                send_queue=self.send_queue,
                receive_queue=self.receive_queue
            ),
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
            logging.warning("[RaspberryCommandsAckProcess] CancelledError fired")
            pass
        finally:
            logging.info("[RaspberryCommandsAckProcess] Closing async process")
            await self.stop()
        
            logging.info("[RaspberryCommandsAckProcess] Finally closed")
            
    async def stop(self):
        self.stop_event.set()
        
        await self.component.stop()
        
        if self.mqtt_client:
            r = await asyncio.shield(self.mqtt_client.close())
            if isinstance(r, Exception):
                logging.exception(r)
            
        
        