import asyncio
import logging

import janus

from libs.component.component import ActuatorComponent
from libs.threads import RThread
from libs.ws.client import WebSocketClient


class ThreadWsComponent(ActuatorComponent):
    """
    A component where the thread is the actuator and the
    websocket is the data broadcaster (send to other and receive from other)
    """
    
    def __init__(self, thread: RThread, ws: WebSocketClient, queue_maxsize=1024):
        super().__init__()
        self.thread = thread
        self.ws = ws
        
        self.q = janus.Queue()
        
        # Set queue
        self.thread.sync_q = self.q.sync_q
        self.ws.async_q = self.q.async_q
        
        # Task
        self.ws_task = None
        
        self.started = False
        
    
    async def _run_ws(self):
        """
        """
        
        try:
            await self.ws.connect()
        except Exception as e:
            logging.error("Can start the websocket")
            print(e)
        finally:
            await self.ws.close()
            
    def start(self):
        """
        Starts the actuactor and submit an async run task
        for the websocket
        """
        
        if self.thread.sync_q is None:
            logging.error("Thread has no queue Set")
            return
        
        if self.ws.async_q is None:
            logging.error("Ws has no queue Set")
            return
        
        self.thread.start()
        logging.info("Thread started")
        
        self.started = True
        
        self.ws_task = asyncio.run(self._run_ws())
        logging.info("Ws scheduled for async")        
        
        
    def join_threads(self):
        """
        Join thread to wait for its'execution
        """
        if not self.started:
            raise Exception("Start not called or has failed")
        
        logging.info("Starting joining thread")
        self.thread.join()
    
    def stop(self):
        """
        Stops the current component
        """
        try:
            # Set flag to true
            self.thread.stop_event.set()
            logging.info("Thread set stop flag to true")
            
            asyncio.run(self.q.aclose())
            logging.info("Scheduled queue to close")
            
            if self.ws:
                self.ws.request_shutdown()
            
            if self.ws_task is not None:
                try:
                    self.ws_task.result()
                except Exception as e:
                    pass
            
            self.join_threads()
            logging.info("Thread has stoped")
        except Exception as e:
            logging.error("Exceptionoccured while stopping component")
            print(e)
    