import asyncio
import logging
import queue


class ThreadCoroutineBridge:
    """
    An unidirectional bridge for thread to send data back to
    
    """
    
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.q_async = asyncio.Queue(loop=self.loop)
        self.q_sync = queue.Queue()
        self.running = True

    def push_from_thread(self, data):
        """Thread-safe push into asyncio queue"""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.q_async.put_nowait, data)
        else:
            logging.warning("Event loop has been closed In thread coroutine bridge")
        
    def push_from_coroutin(self, data):
        """
        Coroutine non blocking pushing data to queue
        """
        asyncio.to_thread(self.q_sync.put_nowait, data)
        