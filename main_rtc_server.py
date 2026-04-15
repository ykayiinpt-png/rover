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

from flask import Flask, request
from flask_socketio import SocketIO, emit

from src.rtc.server_socketio import SocketIoRtcServer

class RtcSocketIOServerProcess(Process):
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
            
        @socketio.on('connect', namespace='/rtc')
        def handle_connect():
            print(f"Client connected: {request.sid}")

        @socketio.on('disconnect', namespace='/rtc')
        def handle_disconnect():
            print(f"Client disconnected: {request.sid}")


        @socketio.on('message', namespace='/rtc')
        def handle_message(data):
            """
            Handle incoming message
            """
            print("\n### Message")
            print(data)
            print("### Message\n")
            
            emit('response', data, broadcast=True, include_self=False, namespace="/rtc")
            
        
        # Background monitor to stop server
        def shutdown_watcher():
            self.stop_event.wait()
            logging.info("[SocketIO] Stopping server...")
            socketio.stop()  # graceful stop

        socketio.start_background_task(shutdown_watcher)

        logging.info("[SocketIO] Server starting...")
            
        socketio.run(app, host=self.host, port=self.port)


class VideoTrackProviderProcess(Process):
    """
    Video Track provider
    """
    
    def __init__(self, server_url="http://localhost:8000"):
        super().__init__()
        
        self.stop_event = Event()
        
        self.server_url = server_url
        
        self.rtc_server = None
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
    
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        stop = asyncio.Event(loop=self.loop)
        
        logging.info("[VideoTrackProviderProcess] Video Track Event loop Set")
        
        self.rtc_server = SocketIoRtcServer(
            self.server_url,
            namespaces=["/rtc"],
            async_event_loop=self.loop
        )
        
        # Handle shutdown
        def handle_shutdown(signum, frame):
            global stop
            
            logging.info(f"[SocketIO] Received signal {signum}, shutting down...")
            self.stop_event.set()
            stop.set()
        
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        
        try:
            self.rtc_server.run()
            
            # We wait until finisshed
            await stop.wait()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            logging.warning("[VideoTrackProviderProcess] CancelledError fired")
            pass
        finally:
            logging.info("[VideoTrackProviderProcess]\n Closing camera async process")
            await self.__stop()
            
            # Exi the  stop waiter
            stop.set()
            
            logging.info("[RtcAsyncProcess] Finally closed")
        
        
    async def __stop(self):
        """
        Stop the camera process
        
        INFORMATION: calling this outside the process will not pass variables value because
        it is a new process that has it's own memory
        """        
        logging.info("[RtcAsyncProcess] Setting stooping down")
        self.stop_event.set()
        
        tasks = []

        if self.rtc_server:
            tasks.append(asyncio.shield(self.rtc_server.stop()))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logging.error(f"[CameraAsyncProcess] Shutdown Error: {r}")

        self.rtc_server = None
        
                
    

def main(host, port, ws_uri):
    server = RtcSocketIOServerProcess(host=host, port=port)
    tracker = VideoTrackProviderProcess(server_url=ws_uri)
    

    try:
        server.start()
        logging.info("[Main] Server process scheduled to start")
        tracker.start()
        logging.info("[Main] Tracker process scheduled to start")
        
        logging.info("[Main] Main process running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("\n[Main] KeyboardInterrupt received. Shutting down...")

        server.terminate()
        tracker.terminate()
        
        server.join(timeout=5)
        tracker.join(timeout=5)


        if server.is_alive():
            logging.warning("[Main] Server Force killing process...")
            server.kill()
            
        if tracker.is_alive():
            logging.warning("[Main] Tracker Force killing process...")
            tracker.kill()

        logging.info("[Main] Clean exit.")
    except Exception as e:
        logging.exception("Exception while running")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host (e.g. 0.0.0.0)"
    )

    parser.add_argument(
        "--port",
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
    
    args = parser.parse_args()
    
    
    try: 
        main(args.host, args.port, args.ws_uri)
    except Exception:
        pass