from asyncio import AbstractEventLoop


class ActuatorComponent:
    """
    Actuator component is a base entity of system that
    create, store, read,exchange data with a remote system
    or another.
    
    Mainly, we have two elements:
    - a thread and a ws
    - a coroutine and a ws
    - a thread and a thread
    - a coroutine and a coroutine
    
    The component that produces the core data is called actuator
    """
    
    def __init__(self, async_event_loop: AbstractEventLoop = None):
        self.started = False
        self.async_event_loop = async_event_loop
    
    def join_threads(self):
        pass
    
    