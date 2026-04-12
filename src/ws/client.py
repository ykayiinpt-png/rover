import asyncio
import logging
import signal
from contextlib import suppress
import json
import time

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidHandshake,
    InvalidURI,
)

from src.thread_bridge import ThreadCoroutineBridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --------------- CLIENT ---------------- #

class WebSocketClient:
    """
    A websocket client. It handles message passage between the actuators
    and the remote server. It uses a producer and consumer approch
    by using a bridge async queue. In the sender method we have an 
    infinite loop seeking for new message to load and send to the remote server; while
    in the recv method as soon as we recev a message we transmit it to the actuator
    through another queue for processing.
    """
    
    def __init__(self, uri: str, async_event_loop: asyncio.AbstractEventLoop):
        self.uri = uri
        self.reconnec_relay = 3
        self.max_reconnec_relay = 30
        self.open_timeout = 10
        self.recv_timeout = 30
        self.ping_interval = 20
        self.ping_timeout = 20
        self.sleep_time_send = 10

        self.async_event_loop = async_event_loop
        
        self.stop_event = asyncio.Event(loop=async_event_loop)
        
        self._ws: websockets.ClientConnection = None
        
        # Queue for communication with an actuator
        #self.async_q = None
        
        self.queue_bridge: ThreadCoroutineBridge = None

    # -------- SIGNAL HANDLING -------- #

    def request_shutdown(self):
        logging.info("Shutdown requested")
        self.stop_event.set()

    # -------- CORE CONNECTION -------- #

    async def connect(self):
        backoff = self.reconnec_relay

        while not self.stop_event.is_set():
            try:
                logging.info(f"Connecting to {self.uri}")

                async with websockets.connect(
                    self.uri,
                    open_timeout=self.open_timeout,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                    close_timeout=5,
                    max_queue=100,
                ) as ws:
                    self._ws = ws
                    logging.info("Connected")

                    backoff = self.reconnec_relay  # reset backoff
                    await self.handle_connection(ws)

            # ---- EXPECTED NETWORK ERRORS ---- #
            except (OSError, InvalidURI, InvalidHandshake) as e:
                logging.error(f"Connection failed: {e}")

            except ConnectionClosedOK:
                logging.info("Connection closed normally")

            except ConnectionClosedError as e:
                logging.warning(f"Connection closed with error: {e}")

            # ---- CATCH-ALL (DO NOT REMOVE) ---- #
            except Exception:
                logging.exception("Unexpected error during connection")

            finally:
                self._ws = None

            if self.stop_event.is_set():
                break

            logging.info(f"Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff, loop=self.async_event_loop)
            backoff = min(backoff * 2, self.max_reconnec_relay)

        logging.info("Connection Success. Exiting connect loop")

    # -------- MESSAGE LOOP -------- #

    async def handle_connection(self, ws):
        receiver_task = asyncio.create_task(self.receiver(ws))
        sender_task = asyncio.create_task(self.sender(ws))

        done, pending = await asyncio.wait(
            [receiver_task, sender_task],
            loop=self.async_event_loop,
            return_when=asyncio.FIRST_EXCEPTION,
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # Propagate exception if any
        for task in done:
            exc = task.exception()
            if exc:
                raise exc

    # -------- RECEIVER -------- #

    async def receiver(self, ws):
        try:
            while not self.stop_event.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=self.recv_timeout, loop=self.async_event_loop)
                    logging.info(f"Remote Received: {msg}")
                    
                    # Add data the brigde sync queue
                    # to the actuator to react
                    await self.queue_bridge.push_from_coroutin(msg)

                except asyncio.TimeoutError:
                    logging.warning("Receive timeout — sending ping")
                    await ws.ping()

                except ConnectionClosed:
                    logging.info("Receiver: connection closed")
                    break

        except asyncio.CancelledError:
            logging.debug("Receiver task cancelled")
            raise

        except Exception:
            logging.exception("Receiver crashed")
            raise

    # -------- SENDER (OPTIONAL) -------- #

    async def sender(self, ws: websockets.ClientConnection):
        try:
            while not self.stop_event.is_set():
                if self.queue_bridge is None:
                    logging.error("async_q has not been set")
                    self.request_shutdown()
                    return
                
                try:
                    data = self.queue_bridge.q_async.get_nowait()
                    if data is not None:
                        message = data
                        print("Data received from queue: ", message)
                        try:
                            start = time.perf_counter()
                            await ws.send(message) # TODO: use text=False to send binary
                            logging.info(f"Sent: {message}")
                            print("Time: ",  time.perf_counter() - start)
                            
                            # Wait
                            await asyncio.sleep(self.sleep_time_send, loop=self.async_event_loop)
                        except ConnectionClosed:
                            logging.info("Sender: connection closed")
                            break
                except asyncio.QueueEmpty:
                    pass
                
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logging.debug("Sender task cancelled")
            raise

        except Exception:
            logging.exception("Sender crashed")
            raise

    # -------- CLEAN SHUTDOWN -------- #

    async def close(self):
        logging.info("Closing client...")

        self.stop_event.set()

        if self._ws:
            try:
                await asyncio.wait_for(self._ws.close(), timeout=5, loop=self.async_event_loop)
                logging.info("WebSocket closed")
            except Exception:
                logging.exception("Error while closing websocket")
