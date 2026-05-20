import os
import sys
import time
import asyncio
import logging
from typing import Dict, Any

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.core.event_bus import get_event_bus
from engine.MemoryVault.memory_manager import MemoryManager
from engine.Layer1_Data_Acquisition.token_juice import TokenJuice

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AutoFetchDaemon")

class AutoFetchDaemon:
    def __init__(self, interval_seconds: int = 20):
        self.interval = interval_seconds
        self.memory_manager = MemoryManager()
        self.event_bus = get_event_bus()

    async def fetch_gdelt_mock(self) -> Dict[str, Any]:
        """
        Mocks fetching data from GDELT or Moltbot since the real endpoints are failing.
        """
        # In reality, this would use engine.Layer1_Data_Acquisition.moltbot_fetcher
        logger.info("Fetching intelligence from sensors...")
        await asyncio.sleep(2) # Simulate network delay
        
        raw_html = "<html><body>BREAKING: Significant naval movements detected near the border. <a href='http://verylongurl.com/a/b/c'>Read more</a></body></html>"
        return {
            "source": "GDELT",
            "title": "Naval Movements Detected",
            "content": raw_html,
            "region": "India-Pakistan"
        }

    async def run_loop(self):
        logger.info(f"Starting AutoFetchDaemon loop (interval: {self.interval}s)...")
        
        while True:
            try:
                # 1. Fetch
                intel = await self.fetch_gdelt_mock()
                
                # 2. Compress via TokenJuice
                compressed_content = TokenJuice.compress(intel['content'])
                logger.info(f"Compressed '{intel['title']}' to {len(compressed_content)} chars.")
                
                # 3. Store in Memory Vault
                doc_id = f"gkg_{int(time.time())}"
                file_path = self.memory_manager.store_intelligence(
                    doc_id=doc_id,
                    title=intel['title'],
                    content=compressed_content,
                    metadata={
                        "source": intel['source'],
                        "region": intel['region'],
                        "tags": ["military", "naval", "border_tension"]
                    }
                )
                
                # 4. Publish Event
                await self.event_bus.publish("NewIntelligenceEvent", {
                    "doc_id": doc_id,
                    "file_path": file_path,
                    "region": intel['region']
                })
                
            except Exception as e:
                logger.error(f"Error in fetch loop: {e}")
                
            await asyncio.sleep(self.interval)

if __name__ == "__main__":
    daemon = AutoFetchDaemon(interval_seconds=10) # 10s for quick testing
    
    # We can run it directly if invoked
    try:
        asyncio.run(daemon.run_loop())
    except KeyboardInterrupt:
        logger.info("AutoFetchDaemon stopped by user.")
