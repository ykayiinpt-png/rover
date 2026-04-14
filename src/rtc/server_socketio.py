from asyncio import AbstractEventLoop
import asyncio
import json
import logging
import queue
import threading
import time
import uuid

from aiortc import RTCConfiguration, RTCIceCandidate, RTCIceServer, RTCPeerConnection, RTCSessionDescription


from src.rtc.track import RtcTrack
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.client import socketioClient
from src.ws.socketio import SocketIoClient


class SocketIoRtcServer:
    """
    A server for serving camera video based on peer to peer connection.
    
    It use the WebRTC protocol and a socketio based signaling server. We only handle
    on client connection for data exchange
    """
    
    def __init__(self, signal_server: str, async_event_loop: AbstractEventLoop):
        self.video_track = None
        self.camera_id = 0
        
        self.lock = asyncio.Lock() # wil be sued later to synchronize
        
        self.loop = async_event_loop
        self.queue_bridge = ThreadCoroutineBridge(async_event_loop)
        
        # The siganling server
        self.ws = SocketIoClient(uri=signal_server, async_event_loop=async_event_loop)
        self.negotiator_thread = RtcNegotiator(self, async_event_loop)
        
        self.ws_task = None
        
        self.negotiator_thread.queue_bridge = self.queue_bridge
        self.ws.queue_bridge = self.queue_bridge
        
     
    async def _run_ws(self):
        """
        Starts the socketio server
        """
        
        try:
            await self.ws.connect()
            logging.info("socketio connected")
        except Exception as e:
            logging.error("Can't start the socketio")
            print(e)
        finally:
            await self.ws.close()   
    
    async def run(self):
        if self.negotiator_thread.queue_bridge is None:
            logging.error("Thread has no queue Set")
            return
        
        if self.ws.queue_bridge is None:
            logging.error("Ws has no queue Set")
            return
        
        self.negotiator_thread.start()
        logging.info("[SocketIoRtcServer] Thread started")
        
        self.ws_task = self.loop.create_task(
            self.ws.connect()
        )
        logging.info("[SocketIoRtcServer] socketio task scheduled")
        
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
            logging.info("[SocketIoRtcServer] Thread set stop flag to true")
            
            #asyncio.run(self.q.aclose())
            logging.info("[SocketIoRtcServer] Scheduled queue to close")
            
            if self.ws:
                self.ws.request_shutdown()
            
            if self.ws_task is not None:
                try:
                    await self.ws_task
                    logging.info("[SocketIoRtcServer] In Stop, Ws task has finished")
                except Exception as e:
                    raise e
                    pass
            
            logging.info("Gatehering pending tasks")
            self.negotiator_thread.clean()
            logging.info("Tasck completed")
            
            await self.join_threads()
            logging.info("[SocketIoRtcServer] Thread has stoped")
            
            if self.video_track is not None:
                try:
                    self.video_track.stop()
                except Exception as e:
                    print("[Exception] e: ", e)

            logging.info("[SocketIoRtcServer] Video Queue Stoped")
        except Exception as e:
            logging.error("[SocketIoRtcServer] Exception occured while stopping component")
            raise e
            
            
            
class RtcNegotiator(RThread):
    """
    Handle the offet, answer, ice candidate negotiation
    between peers
    """
    
    def __init__(self, rtc: SocketIoRtcServer, async_event_loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.rtc = rtc
        self.loop = async_event_loop
        self.pcs = set()
        self.video_track = None
        
        self.loop_tasks = []
        
    
    def run(self):
         # Create a loop for aiortc in the thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.has_client = False
        
        try:
            self.video_track = RtcTrack(self.rtc.camera_id) # TODO: search the video source id
        except Exception as e:
            logging.error("Can't load video track")
            return
        
        try:
            self.loop.run_until_complete(self._run())
        except Exception as e:
            print("Error: ", str(e))
        finally:
            self.loop.close()
        
    
    async def _run(self):
        lock = threading.Lock()
    
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
                    
        # We close all connection
        logging.info("Closing all remaining peers connections")
        await self.clean()
            
        logging.info("All peer connections closed")
            
        # Close the thread loop
        #loop.stop()
            
        # Just to avoid empty queue blocking
        self.queue_bridge.push_from_thread(None)
        
    async def handle_socketio_message(self, message: str, lock: threading.Lock):
        """
        Handle socketio message
        """
        
        if message is None:
            return
        
        data  = dict()
        
        try:
            data = json.loads(message)
        except json.decoder.JSONDecodeError as e:
            logging.warning(f"[SocketIoRtcServer] Can decode message: {message}")
            return
        
        if data.get("type") == "connect":
            print("Data received: ", data)
            # We wonly allow on peer connection
            # So we discard any existing peer connection
            with lock:
                if len(self.pcs) > 0:
                    for pc in list(self.pcs):
                        await self.close_pc(pc)
            
            # Register the new connection
            pc = RTCPeerConnection()
            pc_id = "PeerConnection(%s)" % uuid.uuid4()
            
            self.pcs.add(pc)
            pc.addTransceiver("video", direction="sendonly")
            pc.addTrack(self.video_track)
            
            pc.on("connectionstatechange", lambda: self._handle_event_connection_change(pc))
            pc.on("icecandidate", lambda candidate: self._handle_event_icecandidate(pc, candidate))
            
            self.queue_bridge.push_from_thread(json.dumps({"type": "connect", "status": "ok"}))
            
        elif data.get("type") == "offer":
            # We do receive an offer, we construct a session description
            # from it
            offer = RTCSessionDescription(
                sdp=data["sdp"],
                type=data["type"]
            )
            
            pc = list(self.pcs)[0]
            
            # Set offer and the answer 
            # We wait until it finished
            #asyncio.run_coroutine_threadsafe(
            await self.handle_new_offer(pc, offer)
            #        self.loop
            #)
            
            # Wait for candidates to completes
            # TODO
        elif data.get("type") == "candidate":
            candidate = RtcNegotiator.parse_candidate_dict(data['candidate'])
            
            pc = list(self.pcs)[0]
            print("In candidate")
            
            if pc.remoteDescription is None:
                self.ice_candidates_queue.append(candidate)
            else:
                #asyncio.run_coroutine_threadsafe(
                await self.handle_new_ice_candidate(pc, candidate),
                #    loop=self.loop
                #)
                print("Candidate handled")
            
        
    async def clean(self):
        if self.video_track is not None:
            self.video_track.stop()
            logging.info("[SocketIoRtcServer] Video track stopped")
        
        if self.loop.is_running():
            for task in self.loop_tasks:
                await task
                
    async def handle_new_offer(self, pc: RTCPeerConnection, offer: RTCSessionDescription):
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        self.queue_bridge.push_from_thread(json.dumps({
                "type": answer.type,
                "sdp": answer.sdp
            }))
        
    async def handle_new_ice_candidate(self, pc: RTCPeerConnection, ice_candidate: RTCIceCandidate):
        print("Got ice_candidate: ", ice_candidate)
        await pc.addIceCandidate(ice_candidate)
    
    async def close_pc(self, pc: RTCPeerConnection):
        self.pcs.discard(pc)
        if self.loop.is_running():
            await pc.close()
        
    async def _handle_event_connection_change(self, pc: RTCPeerConnection):
        if pc.connectionState in ["failed", "closed", "disconnected"]:
            if self.loop.is_running():
                await pc.close()
            self.pcs.discard(pc)
        elif pc.connectionState == "connected":
            logging.info("We have a client")
            
    async def _handle_event_icecandidate(self, pc, candidate):
        print("Got Candidate")
        if candidate:
            print("Do have candidate:")
            self.queue_bridge.push_from_thread(json.dumps({
                "type": "candidate",
                "candidate": candidate.to_sdp()
            }))
            
        
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
