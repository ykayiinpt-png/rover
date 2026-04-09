import asyncio
import base64
import time
import json
import aiohttp
import websockets
import cv2
import signal
from av import VideoFrame, open as av_open
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

DJANGO_UPLOAD = "http://localhost:8080/api/upload-frame/"
DRONE_ID = "DRONE_001"
SIGNALING_WS = "ws://127.0.0.1:8000/system/rtc"
VIDEO_FILE = "E:\\N\\droneapp\\notebooks\outputs\\video_1_output_gray_small.mp4"  # path to your video file

# Keep track of all background tasks
pending_tasks = set()
pcs = set()


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

class VideoFileTrack(VideoStreamTrack):
    def __init__(self, path):
        super().__init__()
        self.path = path
        #self.container = av_open(self.path)
        #self.video_stream = self.container.streams.video[0]
        self.cap = cv2.VideoCapture(0)
        self.last_sent = 0
        self.session = aiohttp.ClientSession()
        self._stopped = False
        self._lock = asyncio.Lock()  # optional: avoid concurrent recv calls

    async def send_to_django(self, frame):
        _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        img_base64 = base64.b64encode(buffer).decode("utf-8")
        payload = {
            "image": f"data:image/jpeg;base64,{img_base64}",
            "drone_id": DRONE_ID
        }
        try:
            pass
            #async with self.session.post(DJANGO_UPLOAD, json=payload, timeout=2) as resp:
            #    await resp.text()
            #    print("[OK] Image sent to Remote")
        except Exception:
            print("[AFIL] Image sent to Remote failed...")
            pass

    async def recv(self):
        async with self._lock:
            if self._stopped:
                raise asyncio.CancelledError("Track has been stopped")
            
            
            pts, time_base = await self.next_timestamp()
            ret, frame = self.cap.read()
            if not ret:
                return

            # Convert to RGB for aiortc
            video_frame = frame.to_rgb()
            img = video_frame.to_ndarray()

            now = time.time()
                # 1 frames/sec
            frame_out = VideoFrame.from_ndarray(img, format="rgb24")
            frame_out.pts = pts
            frame_out.time_base = time_base
            return frame_out
            
            print("No Frame available")
            
            # End of file: stop the track
            await self.stop()
            raise asyncio.CancelledError("End of video file")

    async def stop(self):
        print("Stopping VideoFileTrack, Was stopped:", self._stopped)
        if not self._stopped:
            self._stopped = True   
             
            try:
                await self.session.close()
                print("Session has been closed")
                self.container.close()
                print("VideoTrack Stopped")
            except Exception as e:
                print(f"Error closing video container: {e}")
                await super().stop()


async def run():
    # TODO: After think About Replay
    ice_candidate_queue = []
    
    track = VideoFileTrack(VIDEO_FILE)
    pc = RTCPeerConnection()
    pcs.add(pc)
    pc.addTransceiver("video", direction="sendonly")
    pc.addTrack(track)

    async with websockets.connect(SIGNALING_WS) as ws:
        print("[OK] Connected to Websocket")

        @pc.on("icecandidate")
        async def on_ice(candidate):
            if candidate:
                await ws.send(json.dumps({
                    "type": "candidate",
                    "candidate": candidate.to_sdp()
                }))

        # 🔹 Cleanup when connection closes
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state:", pc.connectionState)
            if pc.connectionState in ["failed", "closed", "disconnected"]:
                try:
                    await track.stop()
                    print("Stopping Track")
                    await pc.close()
                    print("Close Pc")
                    pcs.discard(pc)
                    await ws.close()
                    print("WebScket Closed")
                except Exception as e:
                    print("Exception while closing")
                    print(e)
                    pass

        async def handle_signaling():
            async for message in ws:
                data = json.loads(message)
                if data.get("type") == "offer":
                    offer = RTCSessionDescription(
                        sdp=data["sdp"],
                        type=data["type"]
                    )

                    await pc.setRemoteDescription(offer)
                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    
                    while len(ice_candidate_queue) > 0:
                        print("Candidate in list")
                        candidate = ice_candidate_queue.pop(0)
                        await pc.addIceCandidate(candidate)
            
                    await ws.send(json.dumps({
                        "type": answer.type,
                        "sdp": answer.sdp
                    }))
                elif data.get("type") == "candidate":
                    candidate = parse_candidate_dict(data['candidate'])
                    
                    if pc.remoteDescription is None:
                        ice_candidate_queue.append(candidate)
                    else:
                        await pc.addIceCandidate(candidate)
                    

        signaling_task = asyncio.create_task(handle_signaling())

        try:
            await signaling_task
        except asyncio.CancelledError:
            pass
        finally:
            # Cancel all pending tasks before closing
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)

            await track.stop()
            await pc.close()


def main():
    #loop = asyncio.get_event_loop()
    #stop_event = asyncio.Event()

    def shutdown():
        pass#stop_event.set()

    # TODO: to add only on linux
    #for sig in (signal.SIGINT, signal.SIGTERM):
    #    loop.add_signal_handler(sig, shutdown)

    try:
        print("Starting...")
        print("Press Ctrl-C to stop...")
        #loop.run_until_complete(run())
        
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Ctrl-C pressed, shutting down gracefully...")
    finally:

        # Cancel all pending tasks before closing
        for task in pending_tasks:
            task.cancel()
        
        #loop.run_until_complete(loop.shutdown_asyncgens())
        #loop.close()
        print("Shutdown complete.")


if __name__ == "__main__":
    main()