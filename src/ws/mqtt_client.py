import asyncio
from contextlib import suppress
import json
import logging
import time

from aiomqtt import Client, MqttError, Topic

from src.thread_bridge import ThreadCoroutineBridge


class MqttClient:
    """
    A MQTT Broker client.
    """
    
    def __init__(self, uri, port, topics: list[Topic],  async_event_loop: asyncio.AbstractEventLoop):
        self.uri = uri
        self.port = port
        self.topics = topics
        self.recv_timeout = 30
        self.send_timeout = 30
        self.reconnec_relay = 3
        self.max_reconnec_relay = 30
        self.sleep_time_send = 0.1
        
        self._mqtt_client: Client = None
        
        # Async parameters
        self.async_event_loop = async_event_loop
        self.stop_event = asyncio.Event(loop=async_event_loop)
        
        self.queue_bridge: ThreadCoroutineBridge = None
        
    
    #----------------- SIGNAL HANDLING -----------------
    def request_shutdown(self):
        logging.info("Shutting Down the mqtt client")
        self.stop_event.set()
        
    #----------------- CORE CONNECTION -----------------
    
    async def connect(self):
        backoff = self.reconnec_relay
        
        while not self.stop_event.is_set():
            try:
                async with Client(
                    self.uri,
                    port=self.port,
                    timeout=self.recv_timeout
                ) as client:
                    self._mqtt_client = client
                    
                    logging.info("Mqqt Client Connected")
                    
                    for topic in self.topics:
                        print(topic)
                        topic_str = topic +  ""
                        
                        await self._mqtt_client.subscribe(topic)
                        logging.info("[MQTT] Subscribed to topic:")
                    
                    await self.handle_connection(client)
            except Exception as e:
                print(e)
                logging.exception("Unexpected exception occured")
            finally:
                self._mqtt_client = None
                
            if self.stop_event.is_set():
                break
            
            
            logging.info(f"[MQTT] Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff, loop=self.async_event_loop)
            backoff = min(backoff * 2, self.max_reconnec_relay)
            
            
        logging.info("[MQTT] Connected succeffully")
        
    # ----------- MESSAGE LOOP
    
    async def handle_connection(self, client: Client):
        receiver_task = self.async_event_loop.create_task(self.receiver(client))
        sender_task = self.async_event_loop.create_task(self.sender(client))
        
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
    
    async def receiver(self, client: Client):
        try:
            iterator = client.messages.__aiter__()
            print("Iterator: ", iterator)
            
            while not self.stop_event.is_set():
                try:
                    msg = await iterator.__anext__() # timeout=self.recv_timeout)
                    print("[MQTT] message received:", msg,)
                    print("[MQTT] Type of message:", type(msg))
                    print("[MQTT] message received:", msg.payload)
                    
                    # TODO: send back to thread
                except asyncio.TimeoutError:
                    logging.info("Timeout not receiving message")
                    await asyncio.sleep(0.1)
                except StopAsyncIteration:
                    logging.warning("[MQTT] SAsync iteration stopped")
                    break
                except Exception as e:
                    pass 
        except asyncio.CancelledError:
            logging.debug("Receiver task cancelled")
            raise

        except Exception:
            logging.exception("Receiver crashed")
            raise
        
    async def sender(self, client: Client):
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
                            await client.publish(
                                topic=data["topic"],
                                payload=json.dumps(data["payload"]),
                                timeout=self.send_timeout
                                )
                            
                            logging.info(f"Sent: {message}")
                            print("Time: ",  time.perf_counter() - start)
                            
                            # Wait
                            await asyncio.sleep(self.sleep_time_send, loop=self.async_event_loop)
                        except MqttError as e:
                            logging.info("Sender: connection closed: ", e)
                            break
                        except Exception as e:
                            logging.exception("[MQTT] Error at publishing message")
                            pass
                except asyncio.QueueEmpty:
                    pass
                
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logging.debug("[MQTT] Sender task cancelled")
            raise

        except Exception:
            logging.exception("[MQTT] Sender crashed")
            raise
        
    async def close(self):
        logging.info("[MQTT] closing client")
        self.stop_event.set()
        
        if self._mqtt_client:
            try:
                await asyncio.wait_for(self._mqtt_client.unsubscribe(self.topics))
                logging.info("[MQTT] All topics unsubscribed")
            except Exception as e:
                logging.exception("[MQTT] Error while closing Mqtt client")
                
            logging.info("[MQTT] Connection closed")
        
    