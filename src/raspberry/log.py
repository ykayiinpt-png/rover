import multiprocessing


class PiLogger:
    def __init__(self, prefix: str, q: multiprocessing.Queue):
        self.queue = q
        self.prefix = prefix

    def log(self, type, msg):
        payload =  {"topic": "slam/logs", "payload": {"level": type, "msg": f"{self.prefix} {msg}"}}
        self.queue.put(payload)
        
    def info(self, msg):
        self.log("INFO", msg)
        
    def error(self, msg):
        self.log("ERROR", msg)
        
    def warn(self, msg):
        self.log("WARN", msg)