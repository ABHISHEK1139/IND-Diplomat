"""
Interdependence Matrix (Layer 7)
================================
Maps geopolitical dependencies between theaters.
"""

from typing import List, Tuple

# Coupling weights between 0.0 and 1.0
# 150+ country pairs covering all major geopolitical relationships
COUPLING_MATRIX = {
    # ── South Asia ──
    ("IND", "PAK"): 0.85, ("IND", "CHN"): 0.65, ("IND", "USA"): 0.55,
    ("IND", "RUS"): 0.45, ("IND", "LKA"): 0.40, ("IND", "BGD"): 0.50,
    ("IND", "NPL"): 0.35, ("IND", "AFG"): 0.30, ("IND", "MMR"): 0.25,
    ("PAK", "CHN"): 0.75, ("PAK", "USA"): 0.40, ("PAK", "AFG"): 0.55,
    ("PAK", "IRN"): 0.30, ("PAK", "SAU"): 0.35,
    ("BGD", "CHN"): 0.30, ("BGD", "MMR"): 0.30,
    ("LKA", "CHN"): 0.35, ("NPL", "CHN"): 0.40,
    
    # ── East Asia ──
    ("CHN", "TWN"): 0.90, ("CHN", "USA"): 0.70, ("CHN", "JPN"): 0.55,
    ("CHN", "KOR"): 0.45, ("CHN", "PRK"): 0.60, ("CHN", "VNM"): 0.40,
    ("CHN", "PHL"): 0.35, ("CHN", "AUS"): 0.30, ("CHN", "RUS"): 0.50,
    ("CHN", "MNG"): 0.20, ("CHN", "MMR"): 0.30, ("CHN", "KHM"): 0.25,
    ("USA", "TWN"): 0.85, ("USA", "JPN"): 0.75, ("USA", "KOR"): 0.70,
    ("USA", "PRK"): 0.65, ("USA", "PHL"): 0.55, ("USA", "AUS"): 0.70,
    ("JPN", "KOR"): 0.40, ("JPN", "PRK"): 0.55, ("JPN", "RUS"): 0.30,
    ("KOR", "PRK"): 0.95, ("PRK", "RUS"): 0.25,
    ("TWN", "JPN"): 0.40,
    ("AUS", "PHL"): 0.30, ("AUS", "IDN"): 0.30,
    
    # ── Southeast Asia ──
    ("VNM", "PHL"): 0.30, ("VNM", "USA"): 0.25,
    ("IDN", "AUS"): 0.30, ("IDN", "MYS"): 0.30,
    ("THA", "MMR"): 0.35, ("THA", "KHM"): 0.25,
    
    # ── Europe & NATO ──
    ("USA", "RUS"): 0.60, ("USA", "GBR"): 0.75, ("USA", "DEU"): 0.65,
    ("USA", "FRA"): 0.60, ("USA", "UKR"): 0.45, ("USA", "POL"): 0.50,
    ("RUS", "UKR"): 0.95, ("RUS", "GBR"): 0.50, ("RUS", "DEU"): 0.45,
    ("RUS", "FRA"): 0.40, ("RUS", "POL"): 0.55, ("RUS", "BLR"): 0.80,
    ("RUS", "TUR"): 0.35, ("RUS", "KAZ"): 0.30, ("RUS", "FIN"): 0.35,
    ("RUS", "SWE"): 0.30, ("RUS", "NOR"): 0.25,
    ("UKR", "POL"): 0.55, ("UKR", "GBR"): 0.40, ("UKR", "DEU"): 0.40,
    ("UKR", "BLR"): 0.50, ("UKR", "TUR"): 0.25,
    ("GBR", "DEU"): 0.55, ("GBR", "FRA"): 0.55,
    ("DEU", "FRA"): 0.60, ("DEU", "POL"): 0.50,
    ("FRA", "TUR"): 0.25, ("FRA", "ITA"): 0.45,
    ("TUR", "GRC"): 0.50, ("TUR", "IRQ"): 0.30, ("TUR", "SYR"): 0.40,
    ("POL", "BLR"): 0.45,
    
    # ── Middle East ──
    ("USA", "ISR"): 0.85, ("USA", "SAU"): 0.55, ("USA", "IRN"): 0.60,
    ("USA", "IRQ"): 0.35, ("USA", "SYR"): 0.30, ("USA", "ARE"): 0.45,
    ("ISR", "IRN"): 0.80, ("ISR", "PSE"): 0.85, ("ISR", "LBN"): 0.65,
    ("ISR", "SYR"): 0.60, ("ISR", "EGY"): 0.35, ("ISR", "JOR"): 0.30,
    ("ISR", "SAU"): 0.40, ("ISR", "TUR"): 0.30,
    ("IRN", "SAU"): 0.65, ("IRN", "IRQ"): 0.55, ("IRN", "SYR"): 0.60,
    ("IRN", "YEM"): 0.45, ("IRN", "ARE"): 0.35, ("IRN", "TUR"): 0.30,
    ("SAU", "YEM"): 0.60, ("SAU", "QAT"): 0.35, ("SAU", "ARE"): 0.40,
    ("SAU", "EGY"): 0.30,
    ("IRQ", "SYR"): 0.35, ("IRQ", "TUR"): 0.30,
    ("EGY", "ETH"): 0.30, ("EGY", "SDN"): 0.25,
    ("YEM", "OMN"): 0.25,
    ("QAT", "ARE"): 0.30,
    
    # ── Africa ──
    ("EGY", "SDN"): 0.30, ("ETH", "SDN"): 0.30, ("ETH", "SOM"): 0.35,
    ("ETH", "ERI"): 0.35, ("KEN", "SOM"): 0.30,
    ("NGA", "CMR"): 0.25, ("NGA", "TCD"): 0.20,
    ("ZAF", "ZWE"): 0.25,
    ("COD", "RWA"): 0.30, ("COD", "UGA"): 0.25,
    ("LBY", "TCD"): 0.20, ("LBY", "EGY"): 0.20,
    ("MLI", "DZA"): 0.20, ("MLI", "NER"): 0.25,
    
    # ── Americas ──
    ("USA", "CAN"): 0.60, ("USA", "MEX"): 0.45, ("USA", "CUB"): 0.30,
    ("USA", "VEN"): 0.30, ("USA", "BRA"): 0.25, ("USA", "COL"): 0.25,
    ("MEX", "GTM"): 0.20, ("MEX", "CUB"): 0.20,
    ("BRA", "ARG"): 0.30, ("BRA", "VEN"): 0.25,
    ("COL", "VEN"): 0.40, ("COL", "ECU"): 0.20,
    ("ARG", "CHL"): 0.20, ("ARG", "GBR"): 0.20,  # Falklands
    
    # ── Central Asia ──
    ("RUS", "UZB"): 0.25, ("RUS", "TJK"): 0.25,
    ("CHN", "KAZ"): 0.30, ("CHN", "KGZ"): 0.25, ("CHN", "TJK"): 0.30,
    ("AFG", "TJK"): 0.25, ("AFG", "UZB"): 0.20, ("AFG", "IRN"): 0.25,
    ("AFG", "PAK"): 0.55,
    
    # ── Oceania ──
    ("AUS", "NZL"): 0.55, ("AUS", "PNG"): 0.25,
    ("CHN", "PNG"): 0.15, ("CHN", "SLB"): 0.15,
}

def get_weight(country_a: str, country_b: str) -> float:
    pair1 = (country_a.upper(), country_b.upper())
    pair2 = (country_b.upper(), country_a.upper())
    return COUPLING_MATRIX.get(pair1, COUPLING_MATRIX.get(pair2, 0.0))

def get_neighbors(country: str) -> List[Tuple[str, float]]:
    neighbors = []
    cc = country.upper()
    for (a, b), weight in COUPLING_MATRIX.items():
        if a == cc:
            neighbors.append((b, weight))
        elif b == cc:
            neighbors.append((a, weight))
    return neighbors
