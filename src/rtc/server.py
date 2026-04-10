from asyncio import AbstractEventLoop
import asyncio
import json
import logging
import queue
import time
import uuid

from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription


from src.rtc.track import RtcTrack
from src.thread_bridge import ThreadCoroutineBridge
from src.threads import RThread
from src.ws.client import WebSocketClient


class RtcServer:
    """
    A server for serving camera video based on peer to peer connection.
    
    It use the WebRTC protocol and a websocket based signaling server. We only handle
    on client connection for data exchange
    """
    
    def __init__(self, signal_server: str, async_event_loop: AbstractEventLoop):
        try:
            self.video_track = RtcTrack(0) # TODO: search the video source id
        except Exception as e:
            raise e
        
        self.lock = asyncio.Lock() # wil be sued later to synchronize
        
        self.async_event_loop = async_event_loop
        self.queue_bridge = ThreadCoroutineBridge(async_event_loop)
        
        # The siganling server
        self.ws = WebSocketClient(uri=signal_server, async_event_loop=async_event_loop)
        self.negotiator_thread = RtcNegotiator(self, async_event_loop)
        
        self.ws_task = None
        
        self.negotiator_thread.queue_bridge = self.queue_bridge
        self.ws.queue_bridge = self.queue_bridge
        
     
    async def _run_ws(self):
        """
        Starts the websocket server
        """
        
        try:
            await self.ws.connect()
            logging.info("WebSocket connected")
        except Exception as e:
            logging.error("Can't start the websocket")
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
        logging.info("[RtcServer] Thread started")
        
        self.ws_task = self.async_event_loop.create_task(
            self.ws.connect()
        )
        #logging.info("[RtcServer] Websocket task scheduled")
        
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
            logging.info("[RtcServer] Thread set stop flag to true")
            
            #asyncio.run(self.q.aclose())
            logging.info("[RtcServer] Scheduled queue to close")
            
            if self.ws:
                self.ws.request_shutdown()
            
            if self.ws_task is not None:
                try:
                    await self.ws_task
                    logging.info("[RtcServer] In Stop, Ws task has finished")
                except Exception as e:
                    pass
            
            await self.join_threads()
            logging.info("[RtcServer] Thread has stoped")
            
            self.video_track.stop()
            logging.info("[RtcServer] Video Queue Stoped")
        except Exception as e:
            logging.error("[RtcServer] Exception occured while stopping component")
            print(e)
            
            
            
class RtcNegotiator(RThread):
    """
    Handle the offet, answer, ice candidate negotiation
    between peers
    """
    
    def __init__(self, rtc: RtcServer, async_event_loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.rtc = rtc
        self.async_event_loop = async_event_loop
        self.pcs = set()
        
    
    def run(self):
        self.ice_candidates_queue = []
        
        while not self.stop_event.is_set():
            # We wait for message from the queue
            # exchanged with the websocket
            try:
                message = self.queue_bridge.q_sync.get(timeout=1)
            except queue.Empty:
                time.sleep(0.01)
                continue
            
            if message is None:
                return
            
            data = dict()
            
            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                logging.warning(f"[RtcServer] Can decode message: {message}")
            
            if data.get("type") == "connect":
                # We wonly allow on peer connection
                # So we discard any existing peer connection
                if len(self.pcs) > 0:
                    for pc in self.pcs:
                        self.close_pc(pc)
                
                # Register the new connection
                pc = RTCPeerConnection()
                pc_id = "PeerConnection(%s)" % uuid.uuid4()
                
                self.pcs.add(pc)
                pc.addTransceiver("video", direction="sendonly")
                pc.addTrack(self.rtc.video_track)
                
                pc.on("connectionstatechange", lambda: self._handle_event_connection_change(pc))
                pc.on("icecandidate", lambda candidate: self._handle_event_icecandidate(pc, candidate))
                
                self.queue_bridge.q_sync.put(json.dumps({"status": "ok"}))
                
            elif data.get("type") == "offer":
                # We do receive an offer, we construct a session description
                # from it
                offer = RTCSessionDescription(
                    sdp=data["sdp"],
                    type=data["type"]
                )
                
                # Set offer and the answer 
                # We wait until it finished
                asyncio.run_coroutine_threadsafe(self.handle_new_offer(pc, offer)).result()
                
                # Wait for candidates to completes
                # TODO
            elif data.get("type") == "candidate":
                candidate = RtcNegotiator.parse_candidate_dict(data['candidate'])
                    
                if self.pc.remoteDescription is None:
                    self.ice_candidates_queue.append(candidate)
                else:
                    asyncio.run_coroutine_threadsafe(
                        self.handle_new_ice_candidate(pc, candidate),
                        loop=self.async_event_loop
                    ).result()
                    
            time.sleep(0.01)
                    
        # We close all connection
        logging.info("Closing all remaining peers connections")
        for pc in self.pcs:
            self.close_pc(pc)
            
        # Just to avoid empty queue blocking
        self.queue_bridge.q_sync.put(None)
                
    async def handle_new_offer(self, pc: RTCPeerConnection, offer: RTCSessionDescription):
        await pc.setRemoteDescription(offer)
        answer = pc.createAnswer()
        await pc.setLocalDescription(answer)
        
    async def handle_new_ice_candidate(self, pc: RTCPeerConnection, ice_candidate: RTCIceCandidate):
        await pc.addIceCandidate(ice_candidate)
    
    def close_pc(self, pc: RTCPeerConnection):
        asyncio.run_coroutine_threadsafe(pc.close(), self.async_event_loop).result()
        self.pcs.discard(pc)
        
    async def _handle_event_connection_change(self, pc: RTCPeerConnection):
        if pc.connectionState in ["failed", "closed", "disconnected"]:
            await pc.close()
            self.pcs.discard(pc)
            
    async def _handle_event_icecandidate(self, pc, candidate):
        if candidate:
            self.queue_bridge.q_sync.put(json.dumps({
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
