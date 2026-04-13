
"""
GDELT Fetcher - Production Script
=================================
Downloads the latest 15-minute update from GDELT v2.0,
parses events involving key countries, and computes tension scores.

Output: data/tension_history.json
"""

import os
import sys
import requests
import zipfile
import io
import csv
import json
import datetime
from collections import defaultdict

# Add project root to path
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from engine.Layer2_Knowledge.translators.gdelt_translator import GDELTTranslator

# Configuration
GDELT_LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
TARGET_COUNTRIES = ["IND", "USA", "CHN", "PAK", "RUS", "GBR", "CAN", "ISR", "IRN"]
OUTPUT_FILE = os.path.join(BASE, "data", "tension_history.json")

def fetch_latest_url():
    """Get the URL of the latest GDELT CSV."""
    try:
        resp = requests.get(GDELT_LAST_UPDATE_URL)
        if resp.status_code != 200:
            print(f"Failed to fetch last update: {resp.status_code}")
            return None
        
        # Line 1 is export CSV
        line = resp.text.split('\n')[0]
        url = line.split(' ')[2]
        return url
    except Exception as e:
        print(f"Error finding GDELT URL: {e}")
        return None

def download_and_parse(url):
    """Download ZIP, extract CSV, parse rows."""
    print(f"Downloading {url}...")
    try:
        resp = requests.get(url)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            filename = z.namelist()[0]
            with z.open(filename) as f:
                content = f.read().decode('utf-8')
                
        # Parse CSV (Tab separated)
        # GDELT 2.0 CSV has no header. We need to map columns by index.
        # Index 57 = SQLDATE? No, wait. 
        # GDELT 2.0 Event CSV format:
        # 0: GLOBALEVENTID, 1: SQLDATE, ... 
        # 30: GoldsteinScale, 34: AvgTone? 
        # Actually, let's look at documentation standard.
        # But for robust parsing, we'll use a safe index assumption or dict if header existed.
        # Since no header, we use indices.
        
        # Key Indices (Standard GDELT 2.0):
        # 1: SQLDATE (YYYYMMDD)
        # 6: Actor1Code (e.g. IND)
        # 16: Actor2Code
        # 30: GoldsteinScale
        # 32: NumMentions
        # 34: AvgTone
        # 57: SourceURL?
        
        rows = []
        reader = csv.reader(content.splitlines(), delimiter='\t')
        for row in reader:
            if len(row) < 35: continue
            
            try:
                sqldate = row[1]
                actor1 = row[6]
                actor2 = row[16] if len(row) > 16 else ""
                goldstein = float(row[30]) if row[30] else 0.0
                avgtone = float(row[34]) if row[34] else 0.0
                
                rows.append({
                    "SQLDATE": sqldate,
                    "Actor1Name": actor1,
                    "Actor2Name": actor2,
                    "GoldsteinScale": goldstein,
                    "AvgTone": avgtone
                })
            except ValueError:
                continue
                
        return rows
    except Exception as e:
        print(f"Error processing GDELT data: {e}")
        return []

def process_tension(all_events):
    """Compute tension signal for each target country."""
    translator = GDELTTranslator()
    history = {}
    
    # Load existing if available
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                history = json.load(f)
        except:
            history = {}

    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    batch_time = datetime.datetime.now().strftime("%H:%M")
    
    # Filter by country
    country_events = defaultdict(list)
    for event in all_events:
        a1 = event["Actor1Name"]
        a2 = event["Actor2Name"]
        
        for country in TARGET_COUNTRIES:
            if country in a1 or country in a2:
                country_events[country].append(event)
                
    # Update history
    if current_date not in history:
        history[current_date] = {}
        
    for country in TARGET_COUNTRIES:
        events = country_events.get(country, [])
        if not events:
            print(f"No events for {country}")
            continue
            
        signal = translator.translate(events)
        
        # Store minimal data
        if country not in history[current_date]:
             history[current_date][country] = []
             
        history[current_date][country].append({
            "time": batch_time,
            "tension": signal.tension_score,
            "conflict_count": signal.conflict_events,
            "coop_count": signal.cooperation_events,
            "major_actors": signal.major_actors
        })
        
        print(f"{country}: Tension {signal.tension_score} ({len(events)} events)")

    # Save
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    print(f"Saved tension history to {OUTPUT_FILE}")

def main():
    url = fetch_latest_url()
    if url:
        events = download_and_parse(url)
        print(f"Parsed {len(events)} events.")
        process_tension(events)
    else:
        print("Could not get GDELT URL.")

if __name__ == "__main__":
    main()
