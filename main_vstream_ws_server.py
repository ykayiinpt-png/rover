"""
RTC Signaling server

It creates a webscoket server that is used as signaling for
two RTC peers in order to establish a connection. The main function
is to send data to client no processing
"""

import argparse
import asyncio
import logging
from multiprocessing import Event, Process
import signal
import time

from src.vstream.ws.server_socketio import SocketIoVstreamServer


#logging.getLogger("aioice").setLevel(logging.DEBUG)
#logging.getLogger("aiortc").setLevel(logging.DEBUG)


from flask import Flask, request
from flask_socketio import SocketIO, emit

from src.vstream.rtc.server_socketio import SocketIoRtcServer


class VstreamWsSocketIOServerProcess(Process):
    """
    Process to start the flask app
    """
    
    def __init__(self, host="0.0.0.0", port=8000):
        super().__init__()
        self.host = host
        self.port = port
        
        self.stop_event = Event()
        
    def run(self):
        # Create the websoket application and serve
        # on rtc channel
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'your-secret-key'


        socketio = SocketIO(app,cors_allowed_origins="*")
        
        # Signal handling INSIDE process
        def handle_shutdown(signum, frame):
            logging.info(f"[SocketIO] Received signal {signum}, shutting down...")
            self.stop_event.set()

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)


        @socketio.on_error_default
        def default_error_handler(e):
            print(e)
            print(request.event["message"])
            print(request.event["args"])
            
        @socketio.on('connect', namespace='/video')
        def handle_connect():
            print(f"Client connected: {request.sid}")

        @socketio.on('disconnect', namespace='/video')
        def handle_disconnect():
            print(f"Client disconnected: {request.sid}")


        @socketio.on('message', namespace='/video')
        def handle_message(data):
            """
            Handle incoming message
            """
            #print("\n### Message")
            #print(data)
            #print("### Message\n")
            
            emit('response', data, broadcast=True, include_self=False, namespace="/video")
            
        
        # Background monitor to stop server
        def shutdown_watcher():
            self.stop_event.wait()
            logging.info("[SocketIO] Stopping server...")
            socketio.stop()  # graceful stop

        socketio.start_background_task(shutdown_watcher)

        logging.info("[SocketIO] Server starting...")
            
        socketio.run(app, host=self.host, port=self.port, allow_unsafe_werkzeug=True)


class VideoTrackProviderProcess(Process):
    """
    Video Track provider
    """
    
    def __init__(self, server_url="http://localhost:8000", os: str="others"):
        super().__init__()
        
        self.stop_event = Event()
        
        self.server_url = server_url
        
        self.vstream_server = None
        self.os = os
        
        self.loop = None
    
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[VideoTrackProviderProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[VideoTrackProviderProcess] Exception occured")
            raise e
    
    def handle_shutdown(self, signum, frame):
        logging.info(f"[SocketIO] Received signal {signum}, shutting down...")
        self.stop_event.set()
            
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        logging.info("[VideoTrackProviderProcess] Video Track Event loop Set")
        
        self.vstream_server = SocketIoVstreamServer(
            self.server_url,
            namespaces=["/video"],
            async_event_loop=self.loop,
            os=self.os
        )
        
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        try:
            self.vstream_server.run()
            
            # We wait until finisshed
            await self.stop_event.wait()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            logging.warning("[VideoTrackProviderProcess] CancelledError fired")
            pass
        finally:
            logging.info("[VideoTrackProviderProcess]\n Closing camera async process")
            await self.__stop()
        
            logging.info("[VideoTrackProviderProcess] Finally closed")
        
        
    async def __stop(self):
        """
        Stop the camera process
        
        INFORMATION: calling this outside the process will not pass variables value because
        it is a new process that has it's own memory
        """        
        logging.info("[RtcAsyncProcess] Setting stooping down")
        self.stop_event.set()
        
        tasks = []

        if self.vstream_server:
            tasks.append(asyncio.shield(self.vstream_server.stop()))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logging.error(f"[VideoTrackProviderProcess] Shutdown Error: {r}")

        self.vstream_server = None
        
                
    

def main(host, port, ws_uri, features: list[str], os: str):
    server = None
    track_provider = None
    

    try:
        if "server" in features:
            print("Running Server")
            server = VstreamWsSocketIOServerProcess(host=host, port=port)
            server.start()
            logging.info("[Main] Server process scheduled to start")
        
        if "video" in features:
            print("Running video")
            track_provider = VideoTrackProviderProcess(server_url=ws_uri, os=os)
            track_provider.start()
            logging.info("[Main] Track_provider process scheduled to start")
        
        logging.info("[Main] Main process running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("\n[Main] KeyboardInterrupt received. Shutting down...")


        if server is not None:
            server.terminate()
            server.join(timeout=5)
            if server.is_alive():
                logging.warning("[Main] Server Force killing process...")
                server.kill()
                
        if track_provider is not None:
            track_provider.terminate()
            track_provider.join(timeout=5)
            
            if track_provider.is_alive():
                logging.warning("[Main] Track_provider Force killing process...")
                track_provider.kill()

        logging.info("[Main] Clean exit.")
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--io_host",
        type=str,
        default="0.0.0.0",
        help="Host (e.g. 0.0.0.0)"
    )

    parser.add_argument(
        "--io_port",
        type=int,
        default=8000,
        help="Port number (default: 8000)"
    )
    
    parser.add_argument(
        "--ws_uri",
        type=str,
        default="http://127.0.0.1:8000",
        help="Host (e.g. http://127.0.0.1:8000)"
    )
    
    parser.add_argument(
        "--feature",
        type=str,
        action='append',
        choices=["video", "server"],
        required=True,
        help="Features to activate, video processing, Video server transmitter"
    )
    
    parser.add_argument(
        "--os",
        type=str,
        choices=["raspberry_pi", "other"],
        default=["other"],
        help="other uses the VideoCaptaure and raspberry_pi uses the libcamera as background processs"
    )
    
    args = parser.parse_args()
    
    
    try:
        main(host=args.io_host, port=args.io_port, ws_uri=args.ws_uri, features=args.feature , os=args.os)
    except Exception:
        logging.exception("Exception while running")