import asyncio
import logging
from multiprocessing import Event, Process

from src.rtc.client_socketio import SocketIoRtcClient
from src.rtc.server_socketio import SocketIoRtcServer


class CameraAsyncProcess(Process):
    """
    A wrapper for camera processing
    """
    
    def __init__(self):
        super().__init__()
        
        self.stop_event = Event()
        self.rtc_server = None
        self.rtc_client = None
        self.loop = None
    
    def run(self):
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            logging.info("[In CameraAsyncProcess] KeyboardInterrupt received, exiting...")
            print("Loop is running:", self.loop.is_running())
        except Exception as e:
            logging.exception("[In Camera Async] Exception occured")
            raise e
    
    async def main(self):
        loop = asyncio.get_running_loop()
        self.loop = loop
        stop = asyncio.Event(loop=self.loop)
        
        print("Main Run")
        
        self.rtc_server = SocketIoRtcServer(
            "http://localhost:8000",
            namespaces=["/rtc"],
            async_event_loop=self.loop
        )
        self.rtc_client = SocketIoRtcClient(
            "http://localhost:8000",
            namespaces=["/rtc"],
            async_event_loop=self.loop
        )
        
        try:
            await asyncio.gather(
                self.rtc_server.run(),
                self.rtc_client.run(),
                loop=self.loop)
            await stop.wait()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            logging.warning("[RtcAsyncProcess] CancelledError fired")
            pass
        finally:
            logging.info("\n Closing camera async process")
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

        if self.rtc_client:
            tasks.append(asyncio.shield(self.rtc_client.stop()))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logging.error(f"[CameraAsyncProcess] Shutdown Error: {r}")

        self.rtc_server = None
        self.rtc_client = None
        
                
    

