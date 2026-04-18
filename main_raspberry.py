
import argparse
import logging
import os
import sys
import time
import multiprocessing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        print("Setting event policy...")
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    

from src.raspberry.communication.process import CommunicationProcess
from src.raspberry.pi import RaspberryPi

def main(host: str, port: int):
    raspberry_send_queue = multiprocessing.Queue(maxsize=1000)
    raspberry_receive_queue = multiprocessing.Queue(maxsize=1000)
    
    
    communication_process = CommunicationProcess(
        host=host, port=port,
        send_queue=raspberry_send_queue, receive_queue=raspberry_receive_queue
    )

    raspberry = RaspberryPi(send_queue=raspberry_send_queue, receive_queue=raspberry_receive_queue)
    
    

    try:
        print("In try")
        communication_process.start()
        logging.info("[Main] Communication process scheduled to start")
        
        logging.info("[Main] Main process running. Press Ctrl+C to stop.")

        raspberry.run()
    except KeyboardInterrupt:
        logging.info("[Main] KeyboardInterrupt received. Shutting down...")
        raspberry.stop()
    except Exception as e:
        logging.exception("Exception occured While starting raspberry PI4")
        raise e
    finally:
        logging.info("[RaspbarryPi] In finally")
        
        raspberry_send_queue.close()
        raspberry_receive_queue.close()
        
        raspberry_send_queue.join_thread()
        raspberry_receive_queue.join_thread()
        
        logging.info("[RaspbarryPi] Queues closed")
        try:
            if communication_process is not None and communication_process.is_alive():
                communication_process.terminate()
                communication_process.join(timeout=5)


                if communication_process.is_alive():
                    logging.warning("[Main] Server Force killing Communcation process...")
                    communication_process.kill()

            logging.info("[Main] Clean exit.")
        except Exception as e:
            logging.exception("Exception while running")
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mqtt_host",
        type=str,
        default="127.0.0.1",
        help="MQTT Host (e.g. 127.0.0.1)"
    )

    parser.add_argument(
        "--mqtt_port",
        type=int,
        default=1883,
        help="MQTT Port number (default: 1883)"
    )
    
    args = parser.parse_args()
    
    
    try: 
        main(host=args.mqtt_host, port=args.mqtt_port)
    except Exception as e:
        raise e