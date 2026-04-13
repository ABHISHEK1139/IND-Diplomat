
import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

print(f"Sys Path 0: {sys.path[0]}")

try:
    import ind_diplomat.moltbot.fetcher as fetcher_module
    print(f"Module imported: {fetcher_module}")
    print(f"Dir: {dir(fetcher_module)}")
    
    from ind_diplomat.moltbot.fetcher import MoltBotFetcher
    print(f"Class imported: {MoltBotFetcher}")
except Exception as e:
    print(f"Error: {e}")
