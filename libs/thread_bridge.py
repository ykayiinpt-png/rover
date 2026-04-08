import asyncio


class ThreadToCoroutineBridge:
    """
    An unidirectional bridge for thread to send data back to
    
    """
    
    def __init__(self, loop):
        self.loop = loop
        self.queue = asyncio.Queue()
        self.running = True

    def push_from_thread(self, data):
        """Thread-safe push into asyncio queue"""
        asyncio.run_coroutine_threadsafe(self.queue.put(data), self.loop)