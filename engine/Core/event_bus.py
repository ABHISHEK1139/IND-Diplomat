import asyncio
import logging
from typing import Dict, List, Callable, Any, Awaitable

logger = logging.getLogger(__name__)

class EventBus:
    """
    Decoupled Event Bus inspired by OpenHuman.
    Allows modules to publish events and subscribe to them asynchronously.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers = {}
        return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Registers an async handler for a specific event type.
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.debug("[EventBus] Subscribed to %s", event_type)

    async def publish(self, event_type: str, payload: Dict[str, Any]):
        """
        Publishes an event to all registered subscribers concurrently.
        """
        handlers = self.subscribers.get(event_type, [])
        if not handlers:
            logger.debug("[EventBus] No subscribers for %s", event_type)
            return
            
        logger.info("[EventBus] Publishing %s to %d subscribers", event_type, len(handlers))
        
        # Run all handlers concurrently
        tasks = [asyncio.create_task(handler(payload)) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("[EventBus] Handler %s for event %s failed: %s", 
                             handlers[i].__name__, event_type, str(result))

# Singleton accessor
def get_event_bus() -> EventBus:
    return EventBus()
