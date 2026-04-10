import asyncio
import logging

import janus

from src.component.component import ActuatorComponent
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.client import WebSocketClient


class ThreadWsComponent(ActuatorComponent):
    """
    A component where the thread is the actuator and the
    websocket is the data broadcaster (send to other and receive from other)
    """
    
    def __init__(self, thread: RThread, ws: WebSocketClient,
                 queue_bridge: ThreadCoroutineBridge, async_event_loop: asyncio.AbstractEventLoop =None):
        super().__init__(async_event_loop)
        self.thread = thread
        self.ws = ws
        
        # TODO: will be removed
        #self.q = janus.Queue()
        
        # Set queue
        self.queue_bridge = queue_bridge
        self.thread.queue_bridge = self.queue_bridge
        self.ws.queue_bridge = self.queue_bridge
        
        # Task
        self.ws_task = None
        
        self.started = False
        
    
    async def _run_ws(self):
        """
        """
        
        try:
            await self.ws.connect()
            logging.info("In ThreadWs, Ws socket connected")
        except Exception as e:
            logging.error("Can't start the websocket")
            print(e)
        finally:
            await self.ws.close()
            
    async def start(self):
        """
        Starts the actuactor and submit an async run task
        for the websocket
        """
        
        if self.thread.queue_bridge is None:
            logging.error("Thread has no queue Set")
            return
        
        if self.ws.queue_bridge is None:
            logging.error("Ws has no queue Set")
            return
        
        self.ws_task = self.async_event_loop.create_task(self._run_ws(),)
        logging.info("Ws scheduled for async")     
        
        self.thread.start()
        logging.info("Thread started")
        
        self.started = True   
        
        
    def join_threads(self):
        """
        Join thread to wait for its'execution
        
        :returns: a coroutine to await
        """
        if not self.started:
            raise Exception("Start not called or has failed")
        
        logging.info("Starting joining thread")
        return asyncio.to_thread(self.thread.join)
    
    async def stop(self):
        """
        Stops the current component
        """
        try:
            # Set flag to true
            self.thread.stop_event.set()
            logging.info("Thread set stop flag to true")
            
            #asyncio.run(self.q.aclose())
            logging.info("Scheduled queue to close")
            
            if self.ws:
                self.ws.request_shutdown()
            
            if self.ws_task is not None:
                try:
                    await self.ws_task
                    logging.info("In Stop, Ws task has finished")
                except Exception as e:
                    pass
            
            await self.join_threads()
            logging.info("Thread has stoped")
        except Exception as e:
            logging.error("Exception occured while stopping component")
            print(e)
    