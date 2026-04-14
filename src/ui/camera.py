import asyncio
import logging
from multiprocessing import Event, Process

from src.rtc.server_socketio import SocketIoRtcServer


class CameraAsyncProcess(Process):
    """
    A wrapper for camera processing
    """
    
    def __init__(self):
        super().__init__()
        
        self.stop_event = Event()
        self.rtc_server = None
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
            "http://127.0.0.1:8000/rtc",
            self.loop
        )
        
        try:
            await self.rtc_server.run()
            await stop.wait()
        except asyncio.CancelledError:
            # Fallback for Windows (no signal handler)
            logging.info("[Received Inside Camera Porcess] Cancelleation received, exiting...")
            #stop.set()
        except Exception as e:
            logging.exception("In RtcAsyncProcess")
            pass
        finally:
            self.stop_event.set()
            
            logging.info("\n Closing camera async process")            
            try:
                await asyncio.shield(self.rtc_server.stop(), loop=loop)
            except asyncio.CancelledError:
                logging.warning("Cleanup interrupted!")
                
            stop.set()
        
        
    def stop(self):
        """
        Stop the camera process
        
        INFORMATION: calling this outside the process will not pass variables value because
        it is a new process that has it's own memory
        """
        if self.stop_event.is_set():
            logging.info("[RtcAsyncProcess] closing was already set")
            return
        
        logging.info("[RtcAsyncProcess] Setting stooping down")
        self.stop_event.set()
        
        if self.rtc_server:
            if self.loop and self.loop.is_running():
                logging.info(f"[RtcAsyncProcess] Loop is running: {self.loop.is_running()}")
                try:
                    tsks = asyncio.gather([self.rtc_server.stop()], loop=self.loop)
                    for tsk in tsks:
                        tsk.result()
                except Exception as e:
                    logging.exception("Exception while stopping camera process", e)
                    print(e)
        else:
            logging.info("[RtcAsyncProcess] No Rtc server")
                
    

