import logging
import multiprocessing



import logging
import time


from src.threads import RThread


class DataAckSyncMqtt(RThread):
    """
    Acquire data end received data manager.
    
    I t send data from the main autonomous system to the remote Mqtt
    and receive data from the remote mqtt and push it back to main
    autonomous system
    """
    
    def __init__(self, send_queue: multiprocessing.Queue, receive_queue: multiprocessing.Queue):
        super().__init__()
        
        self.counter = 0
        self.send_queue = send_queue
        self.receive_queue = receive_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Check if we have data from the remote server
            if not self.queue_bridge.q_sync.empty():
                payload = self.queue_bridge.q_async.get_nowait()
                print("Data from remote server")
                print(payload)
                print(type(payload))
                
                self.receive_queue.put(payload)
            
            # Check if we do have data to send to the remote server
            if not self.send_queue.empty():
                data = self.send_queue.get_nowait()
                print("Payload do Send: ", data)
                print(type(data))
                
                self.queue_bridge.push_from_thread({
                "topic": data.get("topic", "all"),
                "payload": data.get("payload")
            })
            
            time.sleep(0.001)
        
        logging.info("Thread stop event up")
        
    def stop(self):
        logging.info("[DataAckSyncMqtt] Requested stop...")
        self.stop_event.set()
            
