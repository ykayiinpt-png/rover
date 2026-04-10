import asyncio
import logging
import threading

from src.rtc.server import RtcServer
from src.system.fake_sensor import FakeSensorWrapper
from src.ws.client import WebSocketClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

async def main():    
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    
    wrp = FakeSensorWrapper(
        "wss://echo.websocket.org",
        loop
    )
    #wrp = FakeSensorWrapper("ws://127.0.0.1:8000/mission_data/acquire")
    
    rtcServer = RtcServer("wss://echo.websocket.org", loop)
    
    try:
        #await wrp.run()
        await rtcServer.run()
        
        await stop.wait()
    except asyncio.CancelledError:
        # Fallback for Windows (no signal handler)
        logging.info("Cancelleation received, exiting...")
    finally:
        #await wrp.clean()
        await rtcServer.stop()
    


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        raise e