"""
GDELT Live Sensor
=================
Downloads the latest 15-minute GDELT update, parses events, and outputs RawObservations.
"""

import aiohttp
import zipfile
import io
import csv
import logging
from datetime import datetime, timezone
from typing import List
from dip.core.schema import RawObservation
from dip.layer1_collection.sensors.cameo_config import get_signal_type, get_goldstein

logger = logging.getLogger("Layer1.gdelt_sensor")

GDELT_LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"


class GdeltSensor:
    def __init__(self):
        self.source_id = "GDELT_V2"

    async def fetch(self, country: str = "IND") -> List[RawObservation]:
        """Fetches the latest events from GDELT, filtered by country."""
        observations = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GDELT_LAST_UPDATE_URL) as response:
                    if response.status != 200:
                        logger.error("Failed to get GDELT last update URL.")
                        return []
                    text = await response.text()
                    lines = text.strip().split("\n")
                    if not lines:
                        return []
                    # First line, third column is the CSV zip URL
                    export_url = lines[0].split()[2]
                
                async with session.get(export_url) as response:
                    if response.status != 200:
                        logger.error("Failed to download GDELT zip.")
                        return []
                    zip_data = await response.read()
                    
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                filename = z.namelist()[0]
                with z.open(filename) as f:
                    content = f.read().decode('utf-8')
                    reader = csv.reader(content.splitlines(), delimiter='\t')
                    
                    for row in reader:
                        if len(row) < 58:
                            continue
                        
                        # GDELT v2 column indices
                        actor1_geo = row[37]  # Actor1Geo_CountryCode (FIPS 10-4, but we approximate)
                        actor2_geo = row[44]
                        
                        if country not in actor1_geo and country not in actor2_geo:
                            continue
                            
                        cameo_code = row[26] # EventCode
                        goldstein = float(row[30]) if row[30] else get_goldstein(cameo_code)
                        source_url = row[57] if len(row) > 57 else "GDELT"
                        
                        sig_type = get_signal_type(cameo_code)
                        if sig_type == "SIG_UNKNOWN":
                            continue
                            
                        obs = RawObservation(
                            source_id=self.source_id,
                            source_type="DATASET",
                            content=f"Event {cameo_code} between actors in {actor1_geo} and {actor2_geo}. URL: {source_url}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            country=country,
                            goldstein_score=goldstein,
                            cameo_code=cameo_code
                        )
                        observations.append(obs)
                        
                        # Limit to 100 recent events to prevent overwhelming
                        if len(observations) >= 100:
                            break
                            
        except Exception as e:
            logger.error(f"GDELT fetch error: {e}")
            
        return observations
