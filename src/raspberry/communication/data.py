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
    
    def __init__(self,
                ultrasound_data_sent_queue: multiprocessing.Queue,
                imu_data_send_queue: multiprocessing.Queue,
                odometry_data_sent_queue: multiprocessing.Queue,
                commands_send_queue: multiprocessing.Queue,
                commands_receive_queue: multiprocessing.Queue,
                map_data_send_queue: multiprocessing.Queue):
        super().__init__()
        
        self.counter = 0
        
        self.ultrasound_data_sent_queue = ultrasound_data_sent_queue
        self.imu_data_send_queue = imu_data_send_queue
        self.odometry_data_sent_queue = odometry_data_sent_queue
        self.commands_send_queue = commands_send_queue
        self.commands_receive_queue = commands_receive_queue
        self.map_data_send_queue = map_data_send_queue
        
    def run(self):
        while not self.stop_event.is_set():
            # Check if we have data from the remote server
            if not self.queue_bridge.q_sync.empty():
                payload = self.queue_bridge.q_sync.get_nowait()
                #print("Data from remote server")
                ##print(payload)
                ##print(type(payload))
                
                # Check topic and data back to the
                # slam/rover/commands/remote
            
            # Check if we do have data to send to the remote server
            for q in [
                self.odometry_data_sent_queue, self.commands_send_queue, 
                self.ultrasound_data_sent_queue, self.imu_data_send_queue]:
                if not q.empty():
                    data = q.get_nowait()
                    ##print("Payload do Send: ", data)
                    ##print(type(data))
                    
                    self.queue_bridge.push_from_thread({
                        "topic": data.get("topic", "all"),
                        "payload": data.get("payload")
                    })
            
            time.sleep(0.001)
        
        logging.info("Thread stop event up")
        
    def stop(self):
        logging.info("[DataAckSyncMqtt] Requested stop...")
        self.stop_event.set()
            
