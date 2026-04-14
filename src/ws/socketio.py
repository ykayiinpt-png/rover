import asyncio
from contextlib import suppress
import logging
import time

import socketio

from src.thread_bridge import ThreadCoroutineBridge

class SocketIoClient:
    """
    A socketIo client
    """
    
    def __init__(self, uri, async_event_loop: asyncio.AbstractEventLoop):
        self.uri = uri
        self.recv_timeout = 30
        self.send_timeout = 30
        self.reconnec_relay = 3
        self.max_reconnec_relay = 30
        self.sleep_time_send = 0.1
        
        self._socketIo_client = socketio.AsyncClient()
        
        # Async parameters
        self.async_event_loop = async_event_loop
        self.stop_event = asyncio.Event(loop=async_event_loop)
        
        self.queue_bridge: ThreadCoroutineBridge = None
        
        self.messages = asyncio.Queue(maxsize=1000)
        
    
    #----------------- SIGNAL HANDLING -----------------
    def request_shutdown(self):
        logging.info("Shutting Down the socketio client")
        self.stop_event.set()
        
    #----------------- CORE CONNECTION -----------------
    
    async def connect(self):
        backoff = self.reconnec_relay
        
        while not self.stop_event.is_set():
            try:
                await self._socketIo_client.connect(url=self.uri)
                @self._socketIo_client.on('message')
                def handle_message(msg):
                    try:
                        self.messages.put(msg)
                    except Exception as e:
                        logging.warning('[SocketIO] Exception while adding message to queue')
                
                logging.info("SocketIo Client Connected")
                    
                await self.handle_connection()
            except Exception as e:
                print(e)
                logging.exception("Unexpected exception occured")
            finally:
                self._socketIo_client = None
                
            if self.stop_event.is_set():
                break
            
            
            logging.info(f"[SocketIo] Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff, loop=self.async_event_loop)
            backoff = min(backoff * 2, self.max_reconnec_relay)
            
            
        logging.info("[SocketIo] Connected succeffully")
        
    # ----------- MESSAGE LOOP
    
    async def handle_connection(self):
        receiver_task = self.async_event_loop.create_task(self.receiver())
        sender_task = self.async_event_loop.create_task(self.sender())
        
        # We wait for all the tasks to end
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
    
    async def receiver(self,):
        try:
            
            while not self.stop_event.is_set():
                try:
                    msg = await self.messages.get_nowait()
                    print("[SocketIo] message received:", msg,)
                    print("[SocketIo] Type of message:", type(msg))
                    print("[SocketIo] message received:", msg.payload)
                    
                    # TODO: send back to thread
                except asyncio.QueueEmpty:
                    pass
                except asyncio.TimeoutError:
                    logging.info("Timeout not receiving message")
                    await asyncio.sleep(0.1)
                except StopAsyncIteration:
                    logging.warning("[SocketIo] SAsync iteration stopped")
                    break
                except Exception as e:
                    pass 
        except asyncio.CancelledError:
            logging.debug("Receiver task cancelled")
            raise

        except Exception:
            logging.exception("Receiver crashed")
            raise
        
    async def sender(self):
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
                            await self._socketIo_client.send(data["payload"])
                            
                            logging.info(f"Sent: {message}")
                            print("Time: ",  time.perf_counter() - start)
                            
                            # Wait
                            await asyncio.sleep(self.sleep_time_send, loop=self.async_event_loop)
                        except Exception as e:
                            logging.exception("[SocketIo] Error at publishing message")
                            pass
                except asyncio.QueueEmpty:
                    pass
                
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logging.debug("[SocketIo] Sender task cancelled")
            raise

        except Exception:
            logging.exception("[SocketIo] Sender crashed")
            raise
        
    async def close(self):
        logging.info("[SocketIo] closing client")
        self.stop_event.set()
        
        if self._socketIo_client:
            try:
                await asyncio.wait_for(self._socketIo_client.disconnect())
                logging.info("[SocketIo] Disconnected")
            except Exception as e:
                logging.exception("[SocketIo] Error while closing socketio client")
                
            logging.info("[SocketIo] Connection closed")
        
    