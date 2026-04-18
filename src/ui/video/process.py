import asyncio
import logging
from multiprocessing import Event, Process
import multiprocessing
import signal
import threading
import time

import numpy

from src.vstream.rtc.client_socketio import SocketIoRtcClient
from src.vstream.ws.client_socketio import SocketIoVstreamClient

class RtcTrackComputeThread(threading.Thread):
    """
    Computation on track frame
    """
    def __init__(self, track_queue: multiprocessing.Queue, compute_result_queue: multiprocessing.Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.stop_event = threading.Event()
        self.track_queue = track_queue
        self.compute_result_queue = compute_result_queue
        
    def run(self):
        while not self.stop_event.is_set():
            if not self.track_queue.empty():
                frame = self.track_queue.get()
                #print(frame)
                #logging.info("[RtcTrackComputeThread] Got Frame")
                
                # TODO: compute and push to compute result queue
                self.compute_result_queue.put(frame)
            else:
                #print("RtcTrackComputerThread is empty")
                time.sleep(0.01)
        
        logging.info("[RtcTrackComputeThread] Ended")
        
    def request_stop(self):
        self.stop_event.set()



class VstreamClientProcess(Process):
    """
    Stream with websocket Client
    
    Frame are sent in bytes over a websocket channel
    """
    
    def __init__(self, 
                compute_result_queue: multiprocessing.Queue,  io_url="http://127.0.0.1:8000",
                *args, **kwargs):
        """
        :param compute_result_queue: a multiprocessing queue where frame processing
        result will be sent to
        :param io_url: the socket io server url. It uses the namespace /video to communicate
        """
        
        super().__init__(*args, **kwargs)
        
        self.stop_event = None
        
        self.io_url = io_url
        self.vstream_client = None
        
        """
        Contains frame from the websocket client. It used by the processing logic thread to read
        frame from as input
        """
        self.track_queue = multiprocessing.Queue(maxsize=1000)
        
        self.compute_result_queue = compute_result_queue
        
        self.loop = None
    
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[In VstreamClientProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[In Camera Async] Exception occured")
            raise e
        finally:
            self.track_queue.close()
            self.track_queue.join_thread()
        
    def handle_shutdown(self, signum, frame):
        logging.info(f"[SocketIO] Received signal {signum}, shutting down...")
        self.stop_event.set()
    
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        logging.info("[RtcTrackClientProcess] Video Track Event loop Set")
        
        self.vstream_client = SocketIoVstreamClient(
            self.io_url,
            namespaces=["/video"],
            async_event_loop=self.loop,
            track_queue=self.track_queue
        )
        
        self.computing_thread = RtcTrackComputeThread(
            track_queue=self.track_queue,
            compute_result_queue=self.compute_result_queue
        )
        
        
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        try:
            self.computing_thread.start()
            await self.vstream_client.run()
            
            await self.stop_event.wait()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            logging.warning("[RtcTrackClientProcess] CancelledError fired")
            pass
        finally:
            logging.info("\n Closing camera async process")
            await self.__stop()
            
            # Exi the  stop waiter
            self.stop_event.set()
            
            # Stop the thread
            
            self.computing_thread.request_stop()
            self.computing_thread.join()
            self.close()
            
            logging.info("[RtcTrackClientProcess] Finally closed")
        
        
    async def __stop(self):
        """
        Stop the camera process
        
        INFORMATION: calling this outside the process will not pass variables value because
        it is a new process that has it's own memory
        """        
        logging.info("[RtcTrackClientProcess] Setting stooping down")
        self.stop_event.set()
        
        tasks = []

        if self.vstream_client:
            tasks.append(asyncio.shield(self.vstream_client.stop()))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logging.error(f"[VstreamClientProcess] Shutdown Error: {r}")

        self.vstream_client = None
  

    
class RtcTrackClientProcess(Process):
    """
    Rtc Client
    """
    
    def __init__(self, compute_result_queue: multiprocessing.Queue,  io_url="http://127.0.0.1:8000"):
        super().__init__()
        
        self.stop_event = None
        
        self.io_url = io_url
        self.rtc_client = None
        self.track_queue = multiprocessing.Queue(maxsize=1000)
        self.compute_result_queue = compute_result_queue
        
        self.loop = None
    
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[In RtcTrackClientProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[In Camera Async] Exception occured")
            raise e
        
    def handle_shutdown(self, signum, frame):
        logging.info(f"[RtcTrackClientProcess] Received signal {signum}, shutting down...")
        self.stop_event.set()
    
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.stop_event = asyncio.Event(loop=self.loop)
        
        logging.info("[RtcTrackClientProcess] Video Track Event loop Set")
        
        self.rtc_client = SocketIoRtcClient(
            self.io_url,
            namespaces=["/rtc"],
            async_event_loop=self.loop,
            track_queue=self.track_queue
        )
        
        self.computing_thread = RtcTrackComputeThread(
            track_queue=self.track_queue,
            compute_result_queue=self.compute_result_queue
        )
        
        
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        try:
            #self.computing_thread.start()
            await self.rtc_client.run()
            
            await self.stop_event.wait()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            logging.warning("[RtcTrackClientProcess] CancelledError fired")
            pass
        finally:
            logging.info("\n Closing camera async process")
            await self.__stop()
            
            # Exi the  stop waiter
            self.stop_event.set()
            
            # Stop the thread
            
            self.computing_thread.request_stop()
            self.computing_thread.join()
            
            logging.info("[RtcTrackClientProcess] Finally closed")
        
        
    async def __stop(self):
        """
        Stop the camera process
        
        INFORMATION: calling this outside the process will not pass variables value because
        it is a new process that has it's own memory
        """        
        logging.info("[RtcTrackClientProcess] Setting stooping down")
        self.stop_event.set()
        
        tasks = []

        if self.rtc_client:
            tasks.append(asyncio.shield(self.rtc_client.stop()))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logging.error(f"[RtcTrackClientProcess] Shutdown Error: {r}")

        self.rtc_client = None
        
        
    