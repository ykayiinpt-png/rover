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
    
    def __init__(self, uri, namespaces: list[str], async_event_loop: asyncio.AbstractEventLoop):
        self.uri = uri
        self.recv_timeout = 30
        self.send_timeout = 30
        self.reconnec_relay = 3
        self.max_reconnec_relay = 30
        self.sleep_time_send = 0.0001
        
        self._socketIo_client = socketio.AsyncClient(
            # TODO: logger
            #logger=True, engineio_logger=True
        )
        self.namespaces = namespaces
        self._socketIo_client_wait_task = None
        
        # Async parameters
        self.async_event_loop = async_event_loop
        self.stop_event = asyncio.Event(loop=async_event_loop)
        
        self.queue_bridge: ThreadCoroutineBridge = None
        
        self.messages = asyncio.Queue(maxsize=1000)
        
    
    #----------------- SIGNAL HANDLING -----------------
    def request_shutdown(self):
        logging.info("[SocketIo] Shutting Down the socketio client")
        self.stop_event.set()
        
    #----------------- CORE CONNECTION -----------------
    
    async def handle_message(self, msg):
        try:
            print("\n\n####Message")
            #print(msg)
            print("####Message \n\n")
            
            await self.messages.put(msg)
        except Exception as e:
            logging.warning('[SocketIO] Exception while adding message to queue')
    
    async def connect(self):
        backoff = self.reconnec_relay
        
        while not self.stop_event.is_set():
            try:
                for sp in self.namespaces:
                    self._socketIo_client.on('response', self.handle_message, namespace=sp)
                    
                await self._socketIo_client.connect(url=self.uri, namespaces=self.namespaces)
                self._socketIo_client_wait_task = self.async_event_loop.create_task(self._socketIo_client.wait())
                
                #self._socketIo_client.on('response', self.__handle_message)
                
                await self.handle_connection()
            except asyncio.CancelledError:
                logging.warning("[SocketIo]  cancelled in connect")
                raise
            
            except KeyboardInterrupt:
                logging.exception("[SocketIo]  Keyboard Interupt")
                self.request_shutdown()
            
            except Exception as e:
                print(e)
                logging.exception("[SocketIo] Unexpected exception occured")
  
            if self.stop_event.is_set():
                break
            
            
            logging.info(f"[[SocketIo]] Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff, loop=self.async_event_loop)
            backoff = min(backoff * 2, self.max_reconnec_relay)
            
            
        logging.info("[[SocketIo]] Connected succeffully")
        
    # ----------- MESSAGE LOOP
    
    async def handle_connection(self):
        receiver_task = self.async_event_loop.create_task(self.receiver())
        sender_task = self.async_event_loop.create_task(self.sender())
        
        logging.info("[SocketIo] Tasks created...")
        
        try:
            # We wait for all the tasks to end
            done, pending = await asyncio.wait(
                [receiver_task, sender_task],
                loop=self.async_event_loop,
                return_when=asyncio.FIRST_EXCEPTION,
            )
            
            print("Socket Client IO", [done, pending])
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

            # Propagate exception if any
            for task in done:
                exc = task.exception()
                #print("Exc: ", exec)
                if exc:
                    raise exc
        except asyncio.CancelledError:
            # Clean in case wait_for got fired a cancelled exception
            logging.warning("[SocketIo] Cancelled Exception propagation")
            raise
        finally:
            for task in [receiver_task, sender_task]:
                task.cancel()
            
            results = await asyncio.gather(receiver_task, sender_task, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                    logging.error(f"[Task Error] {r}")
                    
        
            try:
                asyncio.shield(self.close(), loop=self.async_event_loop)
            except Exception:
                logging.warning("[SocketIo] Excption while closing the websocket")
                pass
                    
        logging.info("[SocketIO] Handler Ended")
    
    
    async def receiver(self,):
        try:
            
            while not self.stop_event.is_set():
                try:
                    msg = self.messages.get_nowait()
                    #print("[SocketIo] message received:", msg,)
                    print("[SocketIo] Type of message:", type(msg))
                    
                    # TODO: send back to thread
                    await self.queue_bridge.push_from_coroutin(msg)
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)
                    pass
                except asyncio.TimeoutError:
                    logging.info("Timeout not receiving message")
                except Exception as e:
                    logging.exception(e)
                    pass
                
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logging.warning("[SocketIo] Receiver task cancelled")
            raise

        except Exception:
            logging.exception("Receiver crashed")
            raise
        
    async def sender(self):
        try:
            # We wait for the connection to be established
            # TODO: We can do better by listening to the connect event
            await asyncio.sleep(3)
            
            while not self.stop_event.is_set():
                if self.queue_bridge is None:
                    logging.error("async_q has not been set")
                    self.request_shutdown()
                    return
                
                try:
                    data = self.queue_bridge.q_async.get_nowait()
                    
                    if data is not None:
                        message = data
                        #print("Data received from queue: ", message)
                        try:
                            start = time.perf_counter()
                            await self._socketIo_client.emit("message", data["payload"], namespace=data.get("namespace"))
                            
                            logging.info(f"Sent: {message}")
                            print("Time: ",  time.perf_counter() - start)
                            
                            # Wait
                            await asyncio.sleep(self.sleep_time_send, loop=self.async_event_loop)
                        except Exception as e:
                            logging.exception("[SocketIo] Error at publishing message")
                            pass
                except asyncio.QueueEmpty:
                    pass
                
                await asyncio.sleep(0.001, loop=self.async_event_loop)

        except asyncio.exceptions.CancelledError:
            logging.warning("[SocketIo] Sender task cancelled")
            raise

        except Exception:
            logging.exception("[SocketIo] Sender crashed")
            raise
        
    async def close(self):
        self.stop_event.set()
        
        if self._socketIo_client:
            try:
                if self._socketIo_client_wait_task:
                    self._socketIo_client_wait_task.cancel()
                    
                logging.info("[SocketIo] Disconnecting")
                await self._socketIo_client.disconnect()
                await self._socketIo_client.shutdown()
                logging.info("[SocketIo] Disconnected")
            except asyncio.CancelledError:
                logging.warning("[SocketIo] Cancelled while closing ")
                raise
            except Exception as e:
                logging.exception("[SocketIo] Error while closing socketio client")
                raise
                
            logging.info("[SocketIo] Connection closed")
        
    