import asyncio
import logging
import multiprocessing
import time

from src.raspberry.component.thread_mqtt import ThreadMqttComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.mqtt_client import MqttClient


class RaspberryDataAckMqtt(RThread):
    """
    Data acquisition handler from remote broker.
    
    It acquire sensors data and necessary data for plotting and
    computation.
    """
    
    def __init__(self,
                map_data_queue: multiprocessing.Queue,
                sensors_imu_data_queue: multiprocessing.Queue,
                sensors_ultrasound_data_queue: multiprocessing.Queue,
                odometry_data_queue: multiprocessing.Queue):
        super().__init__()
        
        self.map_result_data_queue = map_data_queue
        self.sensors_ultrasound_data_queue = sensors_ultrasound_data_queue
        self.sensors_imu_data_queue = sensors_imu_data_queue
        self.odometry_data_queue = odometry_data_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Check if we have data from the remote server
            if not self.queue_bridge.q_sync.empty():
                payload: dict = self.queue_bridge.q_sync.get_nowait()
                print("Data from remote server")
                print(payload)
                print(type(payload))
                
                if payload.get("topic") is not None and payload.get("data") is not None:
                    if payload.get("topic") == "slam/sensors/data/ultrasound":
                        # For sensors, we receive somthing like this
                        # for ultrasounds
                        #{'u_f': 3.2060321054356744, 'u_b': 22.689679053200752, 'u_l': 68.26021586457152, 'u_r': 4.3811363690471}
                        data = {}
                        _payload = payload.get("data")
                        
                        if type(_payload) is dict:
                            for k, v in _payload.items():
                                if k in ["u_f", "u_b", "u_l", "u_r"]:
                                    data[k.replace("u_", "")] = v
                            
                            data["time"] = _payload["time"]
                            data["batch_dt"] = _payload["batch_dt"]
        
                            self.sensors_ultrasound_data_queue.put(data)
                            
                    elif payload.get("topic") == "slam/sensors/data/imu":
                        data = {}
                        _payload = payload.get("data")
                        
                        if type(_payload) is dict:
                            self.sensors_imu_data_queue.put(_payload)
                    
                    elif payload.get("topic") == "slam/rover/data/odometry":
                        data = {}
                        _payload = payload.get("data")
                        
                        if type(_payload) is dict:
                            self.odometry_data_queue.put(_payload)
                
                # TODO: push to map queue also
            else:
                #print("Queue for Raspberry is empty")
                pass
            
            time.sleep(0.01)
        
        logging.info("[RaspberryDataAckMqtt] Thread stop event up")
        
    def stop(self):
        logging.info("[RaspberryDataAckMqtt] Requested stop...")
        self.stop_event.set()



class RaspberryDataExchangeProcess(multiprocessing.Process):
    """
    Data exchange with an autonous system, a raspberry pi
    """
    
    def __init__(self, host: str, port: int, 
                map_data_queue: multiprocessing.Queue,
                sensors_imu_data_queue: multiprocessing.Queue,
                sensors_ultrasound_data_queue: multiprocessing.Queue,
                odometry_data_queue=multiprocessing.Queue,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.stop_event = None
        
        self.host = host
        self.port = port
        self.mqtt_client = None
        
        
        self.data_queue = multiprocessing.Queue(maxsize=1000)
        
        self.map_result_data_queue = map_data_queue
        self.sensors_ultrasound_data_queue = sensors_ultrasound_data_queue
        self.sensors_imu_data_queue = sensors_imu_data_queue
        self.odometry_data_queue = odometry_data_queue
        
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[In VstreamClientProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[In Camera Async] Exception occured")
            raise e
        finally:
            self.data_queue.close()
            self.data_queue.join_thread()
            
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        
        self.mqtt_client = MqttClient(
            uri=self.host, port=self.port,
            # Only topics for data reception
            topics=[
                "slam/sensors/data/ultrasound",
                "slam/sensors/data/imu",
                
                # Rover
                "slam/rover/data/odometry",
            ],
            async_event_loop=loop
        )
        
        self.component = ThreadMqttComponent(
            RaspberryDataAckMqtt(
                map_data_queue=self.map_result_data_queue,
                sensors_ultrasound_data_queue=self.sensors_ultrasound_data_queue,
                sensors_imu_data_queue=self.sensors_imu_data_queue,
                odometry_data_queue=self.odometry_data_queue
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
            logging.warning("[RaspberryDataExchangeProcess] CancelledError fired")
            pass
        finally:
            logging.info("[RaspberryDataExchangeProcess] Closing async process")
            await self.stop()
        
            logging.info("[RaspberryDataExchangeProcess] Finally closed")
            
    async def stop(self):
        self.stop_event.set()
        
        await self.component.stop()
        
        if self.mqtt_client:
            r = await asyncio.shield(self.mqtt_client.close())
            if isinstance(r, Exception):
                logging.exception(r)
            
        
        