from asyncio import AbstractEventLoop
import asyncio
import json
import logging
import queue
import subprocess
import threading
import time
import uuid

from aiortc import RTCConfiguration, RTCIceCandidate, RTCIceServer, RTCPeerConnection, RTCSessionDescription
import cv2


from src.vstream.track import RtcTrack
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.socketio import SocketIoClient


class SocketIoVstreamServer:
    """
    A server for serving camera video based on peer to peer connection.
    
    It uses a websocket to send frame to user
    """
    
    def __init__(self, signal_server: str, namespaces: list[str], async_event_loop: AbstractEventLoop, camera_id=0, os="other"):
        self.camera_id = camera_id
        
        self.started = False
        
        self.lock = asyncio.Lock() # wil be sued later to synchronize
        
        self.loop = async_event_loop
        self.queue_bridge = ThreadCoroutineBridge(async_event_loop)
        
        # The siganling server
        self.ws = SocketIoClient(uri=signal_server, namespaces=namespaces, async_event_loop=async_event_loop)
        self.negotiator_thread = RtcNegotiator(camera_id, os=os)
        
        self.ws_task = None
        
        self.negotiator_thread.queue_bridge = self.queue_bridge
        self.ws.queue_bridge = self.queue_bridge
    
    def run(self):
        if self.negotiator_thread.queue_bridge is None:
            logging.error("Thread has no queue Set")
            return
        
        if self.ws.queue_bridge is None:
            logging.error("Ws has no queue Set")
            return
        
        self.negotiator_thread.start()
        logging.info("[SocketIoVstreamServer] Thread started")
        
        self.ws_task = self.loop.create_task(self.ws.connect())
        logging.info("[SocketIoVstreamServer] socketio task scheduled")
        
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
            logging.info("[SocketIoVstreamServer] Thread set stop flag to true")
        
            
            if self.ws_task is not None:
                try:
                    logging.info(f"[SocketIoVstreamServer] Waiting for ws task  (Socket io) task to end: loop is running: {self.loop.is_running()}")
                    await self.ws_task
                except asyncio.CancelledError:
                    logging.warning("[SocketIoVstreamServer] Cancelled in self.stop")
                    raise
                except Exception:
                    logging.exception("[SocketIoVstreamServer] Exception while closing the ws")
                    raise
            logging.info(f"[SocketIoVstreamServer] Waiting for ws (Socket io) task to end: loop is running: {self.loop.is_running()}")
            if self.ws:
                logging.info("[SocketIoVstreamServer] Requesting shutdown")
                self.ws.request_shutdown()
                logging.info("[SocketIoVstreamServer] In Stop, Ws task has finished")
                    
                await self.ws.close()
                logging.info("[SocketIoVstreamServer] In Stop, Ws task close method called")
            
            logging.info("Gatehering pending tasks")
            await self.negotiator_thread.clean()
            logging.info("Tasck completed")
                
            await self.join_threads()
            logging.info("[SocketIoVstreamServer] Thread has stoped")
        except asyncio.CancelledError:
            logging.warning("[SocketIoVstreamServer] Cancellation occured while stopping the RTC Server")
            raise
        except Exception as e:
            logging.exception("[SocketIoVstreamServer] Exception occured while stopping component")
            raise e
        finally:
            logging.info("[SocketIoVstreamServer] Video Queue Stoped")
            
            
class RtcNegotiator(RThread):
    """
    Handle the  server main login against client messages.
    
    It reads frame from the video stream and sent it back
    to a queue. From taht queue the sokcetio client with pick and
    send to server
    """
    
    def __init__(self, camera_id=0, os="raspberry_pi"):
        """
        :param os: On which operating system we are running the the server
        """
        super().__init__()
        
        self.camera_id = camera_id
        self.cap = None
        
        self.os = os
        self.libcamera_stream_process: subprocess.Popen = None
        self.stream = None
        
        self.encode_param = [cv2.IMWRITE_JPEG_QUALITY, 70]
        self.target_size = (320, 240)
    
    
    def run(self):
        try:
            if self.os == "raspberry_pi":
                cmd = [
                    "libcamera-vid",
                    "-t", "0",
                    "--codec", "mjpeg",
                    "--width", "320",
                    "--height", "240",
                    "--nopreview",
                    "-o", "-"
                ]
                self.libcamera_stream_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                self.stream = b""
            else:
                # We instanciate the default camera
                self.cap = cv2.VideoCapture(0)
                print(f"\n\n\n\n\n {self.cap} \n\n\n\n\n\n\n\n\n") 
                
            # The main reader loop         
            while not self.stop_event.is_set():
                #print("In video streaming loop")
                # We can read user redefined paramters from here
                #try:
                #    message = self.queue_bridge.q_sync.get_nowait()
                #    print("Message From server: ", message) 
                
                #except queue.Empty:
                #    # print("Queue Empty")
                #    pass
                
                
                if self.os == "raspberry_pi":
                    self.stream += self.libcamera_stream_process.stdout.read(1024)

                    a = self.stream.find(b'\xff\xd8')  # JPEG start
                    b = self.stream.find(b'\xff\xd9')  # JPEG end

                    if a != -1 and b != -1:
                        jpg_bytes = self.stream[a:b+2]
                        self.stream = self.stream[b+2:]
                        
                        #print("Found Stream: ", jpg_bytes)
                        
                        self.queue_bridge.push_from_thread({
                            "namespace": "/video",
                            "payload": jpg_bytes
                        })
                else:
                    # We handle default camera on  big operating system                    
                    ret, frame = self.cap.read()
                    if not ret:
                        logging.warning("No image frome from video source")
                        time.sleep(2)
                        continue
                    
                    resized = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_AREA)
                    
                    success, buffer = cv2.imencode('.jpg', resized)
                    if success:
                        frame_bytes = buffer.tobytes()
                        self.queue_bridge.push_from_thread({
                            "namespace": "/video",
                            "payload": frame_bytes
                        })
                    else:
                        logging.warning("Encoding frame to jpg failed")
                    
                time.sleep(0.030) # 30 frame per second                
                        
        except Exception:
            logging.exception("[RtcNegotiator] Exception in side RTHread exception")
            raise
        finally:
            # We close all connection
            logging.info("[RtcNegotiator] Closing all remaining peers connections")
            self.clean()
                
            logging.info("All peer connections closed")
                
            # Just to avoid empty queue blocking
            self.queue_bridge.push_from_thread(None)
            
        
    def clean(self):
        self.stop_event.set()
        
        if self.cap is not None:
            self.cap.release()
            
        if self.libcamera_stream_process:
            self.libcamera_stream_process.kill()
            logging.info("[RtcNegotiator] Killing Libcamera vdeo stream process")
            
        logging.debug("[RtcNegotiator] vstream server clean")
                

