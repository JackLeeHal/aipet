import asyncio
from typing import Callable, Dict, List, Type
from .events import Event

class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Callable]] = {}

    def subscribe(self, event_type: Type[Event], callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        event_type = type(event)
        # Notify subscribers for exact type
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                if asyncio.iscoroutinefunction(callback):
                    # We await sequentially to ensure order, but could use asyncio.gather for parallel
                    await callback(event)
                else:
                    callback(event)
