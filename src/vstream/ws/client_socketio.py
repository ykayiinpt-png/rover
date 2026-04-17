from asyncio import AbstractEventLoop
import asyncio
import logging
import multiprocessing
import queue
import time
import cv2
import numpy as np


from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.socketio import SocketIoClient


class SocketIoVstreamClient:
    """
    Rtc client  with an webscoket based signaling server
    """
    
    def __init__(self, signal_server: str, namespaces: list[str], async_event_loop: AbstractEventLoop,  track_queue:  multiprocessing.Queue):
        
        self.started = False
        
        self.lock = asyncio.Lock() # wil be sued later to synchronize
        
        self.loop = async_event_loop
        self.queue_bridge = ThreadCoroutineBridge(async_event_loop)
        
        # The siganling server
        self.ws = SocketIoClient(uri=signal_server, namespaces=namespaces, async_event_loop=async_event_loop)
        self.negotiator_thread = VStreamWsClientNegotiator(track_queue=track_queue)
        
        self.ws_task = None
        
        self.negotiator_thread.queue_bridge = self.queue_bridge
        self.ws.queue_bridge = self.queue_bridge
    
    async def run(self):
        if self.negotiator_thread.queue_bridge is None:
            logging.error("Thread has no queue Set")
            return
        
        if self.ws.queue_bridge is None:
            logging.error("Ws has no queue Set")
            return
        
        self.negotiator_thread.start()
        logging.info("[SocketIoVstreamClient] Thread started")
        
        self.ws_task = self.loop.create_task(self.ws.connect())
        logging.info("[SocketIoVstreamClient] socketio task scheduled")
        
        self.started = True
        
    def join_threads(self):
        """
        Join thread to wait for its'execution
        
        :returns: a coroutine to await
        """
        if not self.started:
            raise Exception("Start not called or has failed")
        
        
        logging.info("Starting joining thread")
        return asyncio.to_thread(self.negotiator_thread.join, 5)
    
    async def stop(self):
        """
        Stops the current component
        """
        try:
            # Set flag to true
            self.negotiator_thread.stop_event.set()
            logging.info("[SocketIoVstreamClient] Thread set stop flag to true")
        
            
            if self.ws_task is not None:
                try:
                    logging.info(f"[SocketIoVstreamClient] Waiting for ws task  (Socket io) task to end: loop is running: {self.loop.is_running()}")
                    await self.ws_task
                except asyncio.CancelledError:
                    logging.warning("[SocketIoVstreamClient] Cancelled in self.stop")
                    raise
                except Exception:
                    logging.exception("[SocketIoVstreamClient] Exception while closing the ws")
                    raise
            logging.info(f"[SocketIoVstreamClient] Waiting for ws (Socket io) task to end: loop is running: {self.loop.is_running()}")
            if self.ws:
                logging.info("[SocketIoVstreamClient] Requesting shutdown")
                self.ws.request_shutdown()
                logging.info("[SocketIoVstreamClient] In Stop, Ws task has finished")
                    
                await self.ws.close()
                logging.info("[SocketIoVstreamClient] In Stop, Ws task close method called")
            
            logging.info("Gatehering pending tasks")
            await self.negotiator_thread.clean()
            logging.info("Tasck completed")
                
            await self.join_threads()
            logging.info("[SocketIoVstreamClient] Thread has stoped")
        except asyncio.CancelledError:
            logging.warning("[SocketIoVstreamClient] Cancellation occured while stopping the RTC Server")
            raise
        except Exception as e:
            logging.exception("[SocketIoVstreamClient] Exception occured while stopping component")
            raise e
        finally:
            if self.video_track is not None:
                try:
                    self.video_track.stop()
                except Exception as e:
                    logging.exception("[SocketIoVstreamClient] Video track stopping exception")
                    print(e)

            logging.info("[SocketIoVstreamClient] Video Queue Stoped")
            
                    
        
class VStreamWsClientNegotiator(RThread):
    """
    Vstream  client Negotiator
    
    The main purpose is to read data from the Websocket
    """
    
    def __init__(self, track_queue:  multiprocessing.Queue):
        super().__init__()
        self.track_queue = track_queue
        
    
    def run(self):
        try:            
            while not self.stop_event.is_set():
                # We wait for message from the queue
                # exchanged with the socketio
                try:
                    message = self.queue_bridge.q_sync.get_nowait()
                    print("\n\n\n\n\n")
                    print("\n\n Data in Negotiator \n\n\n")
                    #print(message)
                    print(type(message))
                    print("\n\n\n\n\n")
                    
                    
                    # Convert the bytes to
                    if not isinstance(message, bytes):
                        logging.warning("Message is not type of byte")
                    else:
                        nparr = np.frombuffer(message, np.uint8)
                        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                        
                        if frame_bgr is not None:
                            rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                            print(f"Format de l'image : {rgb_frame.shape}") # (Hauteur, Largeur, 3)
                            
                            self.track_queue.put(rgb_frame)
                        else:
                            logging.warning("frame_bgr is none")
                    
                except queue.Empty:
                    pass
                
                time.sleep(0.1)
                        
        except Exception:
            logging.warning("[VStreamWsClientNegotiator] Cancelllation in side RTHread exception")
            raise
        finally:
            # We close all connection
            logging.info("[VStreamWsClientNegotiator] Closing all remaining peers connections")
            self.clean()
                
            logging.info("All peer connections closed")
                
            # Just to avoid empty queue blocking
            self.queue_bridge.push_from_thread(None)
            
    
    def clean(self):
        self.stop_event.set()
          
        logging.warning("[VStreamWsClientNegotiator] cleaned")
        
