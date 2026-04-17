import asyncio
import logging
import os
import sys
import threading

from src.vstream.rtc.server import RtcServer
from src.system.fake_sensor import FakeSensorWrapper
from src.system.fake_sensor_mqtt import FakeSensorMqttWrapper
from src.ws.client import WebSocketClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        print("Setting event policy...")
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
        
        
async def main():
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    
    #wrp = FakeSensorWrapper(
    #    "wss://echo.websocket.org",
    #    loop
    #)
    #wrp = FakeSensorWrapper(
    #    "ws://127.0.0.1:8000/mission_data/acquire",
    #    loop
    #)
    
    wrp = FakeSensorMqttWrapper(
        uri="127.0.0.1",
        port=1883,
        async_event_loop=loop
    )
    
    #rtcServer = RtcServer("wss://echo.websocket.org", loop)
    #rtcServer = RtcServer("ws://127.0.0.1:8000/system/rtc", loop)
    try:
        await wrp.run()
        #await rtcServer.run()
        
        await stop.wait()
    except asyncio.CancelledError:
        # Fallback for Windows (no signal handler)
        logging.info("Cancelleation received, exiting...")
    finally:
        await wrp.clean()
        print("Loop Event is alive: ", loop.is_running())
        #await rtcServer.stop()
    


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        raise e