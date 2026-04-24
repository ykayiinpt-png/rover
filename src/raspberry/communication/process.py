import asyncio
import logging
import multiprocessing
import signal



import asyncio
import logging


from src.raspberry.communication.data import DataAckSyncMqtt
from src.raspberry.component.thread_mqtt import ThreadMqttComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.ws.mqtt_client import MqttClient


class CommunicationProcess(multiprocessing.Process):
    """
    Process to handle the communication between
    an autonous sytem and a remote observabation center.
    
    It has been designed in order to be separated from the main
    process of the raspberry pi because the raspberry will have to 
    do a lot of computation and we do not want to await for long 
    data from brokers
    """
    
    def __init__(self, host: str, port: int, 
                send_queue: multiprocessing.Queue, receive_queue: multiprocessing.Queue,
                *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.host = host
        self.port = port
        
        self.send_queue = send_queue
        self.receive_queue = receive_queue
        
        self.mqtt_client: MqttClient = None
    
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[CommunicationProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[CommunicationProcess] Exception occured")
            raise e
        
    def handle_shutdown(self, signum, frame):
        logging.info(f"[SocketIO] Received signal {signum}, shutting down...")
        self.stop_event.set()
    
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        logging.info("[CommunicationProcess] Event loop Set")
    
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        self.mqtt_client = MqttClient(
            uri=self.host, port=self.port,
            # Only topics for data reception
            topics=["slam/commands/raspberry"],
            async_event_loop=loop
        )
        
        self.component = ThreadMqttComponent(
            DataAckSyncMqtt(
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
            logging.warning("[CommunicationProcess] CancelledError fired")
            pass
        finally:
            logging.info("[CommunicationProcess] Closing async process")
            await self.stop()
        
            logging.info("[CommunicationProcess] Finally closed")
            
    async def stop(self):
        self.stop_event.set()
        
        await self.component.stop()
        
        if self.mqtt_client:
            r = await asyncio.shield(self.mqtt_client.close())
            if isinstance(r, Exception):
                logging.exception(r)