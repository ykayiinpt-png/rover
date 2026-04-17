from asyncio import AbstractEventLoop
import asyncio
import json
import logging
import multiprocessing
import queue
import threading
import uuid

from aiortc import MediaStreamTrack, RTCConfiguration, RTCIceCandidate, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.rtcrtpreceiver import RemoteStreamTrack
from av import VideoFrame
import numpy

from src.vstream.rtc.server_socketio import SocketIoRtcServer
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.socketio import SocketIoClient


class SocketIoRtcClient:
    """
    Rtc client  with an webscoket based signaling server
    """
    
    def __init__(self, signal_server: str, namespaces: list[str], async_event_loop: AbstractEventLoop,  track_queue:  multiprocessing.Queue):
        self.video_track = None
        self.camera_id = 0
        
        self.started = False
        
        self.lock = asyncio.Lock() # wil be sued later to synchronize
        
        self.loop = async_event_loop
        self.queue_bridge = ThreadCoroutineBridge(async_event_loop)
        
        # The siganling server
        self.ws = SocketIoClient(uri=signal_server, namespaces=namespaces, async_event_loop=async_event_loop)
        self.negotiator_thread = RtcClientNegotiator(self, async_event_loop, track_queue=queue)
        
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
        logging.info("[SocketIoRtcClient] Thread started")
        
        self.ws_task = self.loop.create_task(self.ws.connect())
        logging.info("[SocketIoRtcClient] socketio task scheduled")
        
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
            logging.info("[SocketIoRtcClient] Thread set stop flag to true")
        
            
            if self.ws_task is not None:
                try:
                    logging.info(f"[SocketIoRtcClient] Waiting for ws task  (Socket io) task to end: loop is running: {self.loop.is_running()}")
                    await self.ws_task
                except asyncio.CancelledError:
                    logging.warning("[SocketIoRtcClient] Cancelled in self.stop")
                    raise
                except Exception:
                    logging.exception("[SocketIoRtcClient] Exception while closing the ws")
                    raise
            logging.info(f"[SocketIoRtcClient] Waiting for ws (Socket io) task to end: loop is running: {self.loop.is_running()}")
            if self.ws:
                logging.info("[SocketIoRtcClient] Requesting shutdown")
                self.ws.request_shutdown()
                logging.info("[SocketIoRtcClient] In Stop, Ws task has finished")
                    
                await self.ws.close()
                logging.info("[SocketIoRtcClient] In Stop, Ws task close method called")
            
            logging.info("Gatehering pending tasks")
            await self.negotiator_thread.clean()
            logging.info("Tasck completed")
                
            await self.join_threads()
            logging.info("[SocketIoRtcClient] Thread has stoped")
        except asyncio.CancelledError:
            logging.warning("[SocketIoRtcClient] Cancellation occured while stopping the RTC Server")
            raise
        except Exception as e:
            logging.exception("[SocketIoRtcClient] Exception occured while stopping component")
            raise e
        finally:
            if self.video_track is not None:
                try:
                    self.video_track.stop()
                except Exception as e:
                    logging.exception("[SocketIoRtcClient] Video track stopping exception")
                    print(e)

            logging.info("[SocketIoRtcClient] Video Queue Stoped")
            
                    
        
class RtcClientNegotiator(RThread):
    """
    Rtc client Negotiator
    """
    
    def __init__(self, rtc: SocketIoRtcServer, async_event_loop: asyncio.AbstractEventLoop, track_queue:  multiprocessing.Queue):
        super().__init__()
        self.rtc = rtc
        self.loop = None #async_event_loop
        
        self.loop_tasks = []
        
        self.pc = None
        self.track_queue = track_queue
        self.stop_handling_track_event = threading.Event()
        self.handle_track_task: asyncio.Task = None
        self.track_queue = track_queue
        
    
    def run(self):
        # Create a loop for aiortc in the thread
        # This maintain aiortc logics in the same event loop 
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        
        try:
            asyncio.run(self._run())
        except Exception as e:
            logging.exception("Running: ")
            raise
        finally:
            logging.info("Closing Rtc negotiator event loop...")
            self.loop.stop()
        
    
    async def _run(self):
        try:
            lock = threading.Lock()
            
            
                
            await asyncio.sleep(2)
            
            
            # Send the connect to the signaling server to initialize the 
            # peer connections
            self.queue_bridge.push_from_thread({
                "namespace": "/rtc",
                "payload": {
                    "type": "connect",
                }
            })
            
            self.ice_candidates_queue = []
            
            while not self.stop_event.is_set():
                # We wait for message from the queue
                # exchanged with the socketio
                try:
                    message = self.queue_bridge.q_sync.get_nowait()
                    
                    await self.handle_socketio_message(message, lock)
                except queue.Empty:
                    pass
                await asyncio.sleep(0.1)
                        
        except asyncio.CancelledError:
            logging.warning("[RtcClientNegotiator] Cancelllation in side RTHread exception")
            raise
        finally:
            # We close all connection
            logging.info("[RtcClientNegotiator] Closing all remaining peers connections")
            await self.clean()
                
            logging.info("All peer connections closed")
                
            # Just to avoid empty queue blocking
            self.queue_bridge.push_from_thread(None)
            
            # Close the thread loop
            self.loop.stop()
            
        
    async def handle_track(self, track: RemoteStreamTrack):
        print("\n\nTrack Received")
        print(track)
        print(track.kind)
        print("\n\n\n")
                
        # We stop the already running task
        
        await asyncio.sleep(1)
                
                # And cancel it
        if self.handle_track_task is not None:
            self.handle_track_task.cancel()
        
        if self.stop_handling_track_event.is_set():
            self.stop_handling_track_event.clear()
            
        
        while not self.stop_handling_track_event.is_set():
            print("In While loop")
            try:
                logging.info("Waiting for frame...")
                frame = await track.recv()
                frame_count += 1
                logging.info(f"Received frame {frame_count}")
                
                if isinstance(frame, VideoFrame):
                    logging.info(f"Frame type: VideoFrame, pts: {frame.pts}, time_base: {frame.time_base}")
                    frame = frame.to_ndarray(format="bgr24")
                elif isinstance(frame, numpy.ndarray):
                    logging.info(f"Frame type: numpy array")
                else:
                    logging.info(f"Unexpected frame type: {type(frame)}")
                    continue
                
                if self.track_queue is not None:
                    self.track_queue.put_nowait(frame)
                    
                await asyncio.sleep(1)
                
            except asyncio.TimeoutError:
                logging.info("Timeout waiting for frame, continuing...")
            except asyncio.CancelledError:
                logging.info("Cancelled track consumption")
                pass
            except Exception as e:
                logging.exception("Error while receiving track")
                print(e)
                break
            
        # We reset
        self.stop_handling_track_event.clear()
        print("Handling track finised")
    
    async def handle_socketio_message(self, message, lock: threading.Lock):
        """
        Handle socketio message
        """
        
        if message is None:
            return
        
        data  = dict()
        if type(message) == "str":
            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                logging.warning(f"[SocketIoRtcClient] Can decode message: {message}")
                return
        else:
            data = message
            
        print("In handling socket io:", message)
            
        if data.get("type") == "connect":
            print("Data received: Connect ", data)
            # We wonly allow on peer connection
            # So we discard any existing peer connection
            with lock:
                if self.pc is not None:
                    await self.close_pc(self.pc)
                    
            self.pc = RTCPeerConnection(RTCConfiguration(
                iceServers=[]
            ))
            self.pc.addTransceiver('audio', direction='inactive')
            self.pc.addTransceiver("video", direction="recvonly")
            
            self.pc.on("iceconnectionstatechange", self.handle_event_connection_change)
            self.pc.on("icecandidate", self.handle_event_icecandidate)
            self.pc.on("track", self.handle_track)
                
            # Create offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            
            while self.pc.iceGatheringState != "complete":
                print("Gathering ICE...")
                await asyncio.sleep(0.1)

            print("ICE gathering complete")
            
            print("\n\n\n\n\\n\n\n\n\n")
            print(self.pc.localDescription.sdp)
            print("\n\n\n\n\\n\n\n\n\n")
        
                
            # Send the offer to the signaling server
            self.queue_bridge.push_from_thread({
                "namespace": "/rtc",
                "payload": {
                    "type": self.pc.localDescription.type,
                    "sdp": self.pc.localDescription.sdp
                }
            })
        
        elif data.get("type") == "answer":
            print("Data received Answer: ", data)
            
            # Set the remote connection
            await self.pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type="answer"))
                        
        elif data.get("type") == "candidate":
            candidate = RtcClientNegotiator.parse_candidate_dict(data['candidate'])
            
            if self.pc.remoteDescription is None:
                self.ice_candidates_queue.append(candidate)
            else:
                for ice in self.ice_candidates_queue:
                    await self.handle_new_ice_candidate(self.pc, ice)
                
                await self.handle_new_ice_candidate(self.pc, candidate)
            
        
    async def clean(self):
        self.stop_handling_track_event.set()
        
        if self.pc is not None:
            await self.pc.close()
            logging.info("[SocketIoRtcClient] Video track stopped")
            
        if self.handle_track_task is not None:
            self.handle_track_task.cancel()
            self.loop_tasks.append(self.handle_track_task)
            
        if self.loop and self.loop.is_running():
            for task in self.loop_tasks:
                try:
                    await task
                except Exception as e:
                    logging.warning("[RtcClientNegotiator] Exception while waiting for task in loop tasks")
                    print(e)
        else:
            logging.warning("[RtcClientNegotiator] Event loop not running...")
        
    async def handle_event_connection_change(self):
        print("Connection state: ", self.pc.connectionState)
        if self.pc.connectionState in ["failed", "closed", "disconnected"]:
            if self.loop.is_running():
                await self.pc.close()
                
        elif self.pc.connectionState == "connected":
            logging.info("[RtcClientNegotiator] Connected")
    
    async def handle_new_ice_candidate(self, ice_candidate: RTCIceCandidate):
        print("Got ice_candidate: ", ice_candidate)
        await self.pc.addIceCandidate(ice_candidate)    
            
    async def handle_event_icecandidate(self, candidate):
        print("Got Candidate")
        if candidate:
            print("Do have candidate:")
            self.queue_bridge.push_from_thread({
                "namespace": "/rtc",
                "payload": {
                    "type": "candidate",
                    "candidate": candidate.to_sdp()
                }
            })
            
        
    def parse_candidate_dict(data):
        # 'data' is the inner dictionary from your JSON
        # e.g., data["candidate"] = "candidate:2272122186 1 udp..."
        parts = data["candidate"].split()
        
        # Basic mapping of the standard ICE candidate format:
        # 0: foundation, 1: component, 2: protocol, 3: priority, 4: ip, 5: port, 7: type
        return RTCIceCandidate(
            foundation=parts[0].replace("candidate:", ""),
            component=int(parts[1]),
            protocol=parts[2],
            priority=int(parts[3]),
            ip=parts[4],
            port=int(parts[5]),
            type=parts[7],
            sdpMid=data.get("sdpMid"),
            # sdpMLineIndex=data.get("sdpMLineIndex")
        )

