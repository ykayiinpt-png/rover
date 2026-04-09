import logging

from libs.system.fake_sensor import FakeSensorWrapper
from libs.ws.client import WebSocketClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def main():    
    #wrp = FakeSensorWrapper("wss://echo.websocket.org")
    wrp = FakeSensorWrapper("ws://127.0.0.1:8000/mission_data/acquire")
    
    
    try:
        wrp.component.start()
        wrp.component.join_threads()
    except KeyboardInterrupt:
        # Fallback for Windows (no signal handler)
        logging.info("KeyboardInterrupt received, exiting...")
        wrp.component.stop()


if __name__ == "__main__":
    main()