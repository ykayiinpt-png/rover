import asyncio
import logging

import janus

from src.raspberry.component.component import ActuatorComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.mqtt_client import MqttClient


class ThreadMqttComponent(ActuatorComponent):
    """
    A component where the thread is the actuator and the
    mqtt client is the data broadcaster (send to other and receive from other)
    """
    
    def __init__(self, thread: RThread, mqtt: MqttClient,
                 queue_bridge: ThreadCoroutineBridge, async_event_loop: asyncio.AbstractEventLoop =None):
        super().__init__(async_event_loop)
        self.thread = thread
        self.mqtt = mqtt
        
        # Set queue
        self.queue_bridge = queue_bridge
        self.thread.queue_bridge = self.queue_bridge
        self.mqtt.queue_bridge = self.queue_bridge
        
        # Task
        self.mqtt_task = None
        
        self.started = False
        
    
    async def _run_mqtt(self):
        """
        """
        
        try:
            await self.mqtt.connect()
            logging.info("[MQTT] In ThreadMqtt, Mqtt socket connected")
        except Exception as e:
            logging.error("[MQTT] Can't start the Mqtt client")
            #print(e)
        finally:
            await self.mqtt.close()
            
    async def start(self):
        """
        Starts the actuactor and submit an async run task
        for the MQTT client
        """
        
        if self.thread.queue_bridge is None:
            logging.error("[MQTT] Thread has no queue Set")
            return
        
        if self.mqtt.queue_bridge is None:
            logging.error("[MQTT] Mqtt client queue has no queue Set")
            return
        
        self.mqtt_task = self.async_event_loop.create_task(self._run_mqtt(),)
        logging.info("[MQTT] MqttClient scheduled for async")     
        
        self.thread.start()
        logging.info("[MQTT] Thread started")
        
        self.started = True   
        
        
    def join_threads(self):
        """
        Join thread to wait for its'execution
        
        :returns: a coroutine to await
        """
        if not self.started:
            raise Exception("[MQTT] Start not called or has failed")
        
        logging.info("[MQTT] Starting joining thread")
        return asyncio.to_thread(self.thread.join)
    
    async def stop(self):
        """
        Stops the current component
        """
        try:
            # Set flag to true
            self.thread.stop_event.set()
            logging.info("[MQTT] Thread set stop flag to true")
            
            #asyncio.run(self.q.aclose())
            logging.info("[MQTT] Scheduled queue to close")
            
            if self.mqtt:
                self.mqtt.request_shutdown()
            
            if self.mqtt_task is not None:
                try:
                    await self.mqtt_task
                    logging.info("[MQTT] In Stop, Mqtt task has finished")
                    
                    await self.mqtt.close()
                    logging.info("[MQTT] Mqtt client has been closed successfully.")
                except Exception as e:
                    pass
            
            await self.join_threads()
            logging.info("[MQTT] Thread has stoped")
        except Exception as e:
            logging.error("[MQTT] Exception occured while stopping component")
            #print(e)
    