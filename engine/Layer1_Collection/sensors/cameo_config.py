"""
CAMEO Lookup Tables — Official GDELT Reference Data
=====================================================

Source: https://www.gdeltproject.org/data/lookups/

Tables:
    CAMEO_COUNTRY_CODES     — 3-char country/region code → label
    CAMEO_EVENT_CODES       — numeric event code → description
    CAMEO_GOLDSTEIN         — numeric event code → Goldstein scale score
    CAMEO_ACTOR_TYPES       — 3-char actor type → label
    CAMEO_RELIGIONS         — 3-char religion code → label
    CAMEO_REGIONAL_CODES    — set of region codes (non-country)

These tables are canonical. Do not modify unless GDELT updates
the official lookup files.
"""

from __future__ import annotations

from typing import Dict, Set

# =====================================================================
# Regional codes (NOT actual countries — filter from country-level analysis)
# =====================================================================

CAMEO_REGIONAL_CODES: Set[str] = {
    "WSB", "BAG", "GZS", "AFR", "ASA", "BLK", "CRB", "CAU", "CFR", "CAS",
    "CEU", "EIN", "EAF", "EEU", "EUR", "LAM", "MEA", "MDT", "NAF", "NMR",
    "PGS", "SCN", "SAM", "SAS", "SEA", "SAF", "WAF", "WST",
}

# =====================================================================
# Country Codes (CAMEO.country.txt)
# =====================================================================

CAMEO_COUNTRY_CODES: Dict[str, str] = {
    "AFG": "Afghanistan", "ALA": "Aland Islands", "ALB": "Albania",
    "DZA": "Algeria", "ASM": "American Samoa", "AND": "Andorra",
    "AGO": "Angola", "AIA": "Anguilla", "ATG": "Antigua and Barbuda",
    "ARG": "Argentina", "ARM": "Armenia", "ABW": "Aruba",
    "AUS": "Australia", "AUT": "Austria", "AZE": "Azerbaijan",
    "BHS": "Bahamas", "BHR": "Bahrain", "BGD": "Bangladesh",
    "BRB": "Barbados", "BLR": "Belarus", "BEL": "Belgium",
    "BLZ": "Belize", "BEN": "Benin", "BMU": "Bermuda",
    "BTN": "Bhutan", "BOL": "Bolivia", "BIH": "Bosnia and Herzegovina",
    "BWA": "Botswana", "BRA": "Brazil", "VGB": "British Virgin Islands",
    "BRN": "Brunei Darussalam", "BGR": "Bulgaria", "BFA": "Burkina Faso",
    "BDI": "Burundi", "KHM": "Cambodia", "CMR": "Cameroon",
    "CAN": "Canada", "CPV": "Cape Verde", "CYM": "Cayman Islands",
    "CAF": "Central African Republic", "TCD": "Chad", "CHL": "Chile",
    "CHN": "China", "COL": "Colombia", "COM": "Comoros",
    "COD": "Democratic Republic of the Congo",
    "COG": "People's Republic of the Congo",
    "COK": "Cook Islands", "CRI": "Costa Rica", "CIV": "Ivory Coast",
    "HRV": "Croatia", "CUB": "Cuba", "CYP": "Cyprus",
    "CZE": "Czech Republic", "DNK": "Denmark", "DJI": "Djibouti",
    "DMA": "Dominica", "DOM": "Dominican Republic", "TMP": "East Timor",
    "ECU": "Ecuador", "EGY": "Egypt", "SLV": "El Salvador",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "EST": "Estonia",
    "ETH": "Ethiopia", "FRO": "Faeroe Islands", "FLK": "Falkland Islands",
    "FJI": "Fiji", "FIN": "Finland", "FRA": "France",
    "GUF": "French Guiana", "PYF": "French Polynesia", "GAB": "Gabon",
    "GMB": "Gambia", "GEO": "Georgia", "DEU": "Germany",
    "GHA": "Ghana", "GIB": "Gibraltar", "GRC": "Greece",
    "GRL": "Greenland", "GRD": "Grenada", "GLP": "Guadeloupe",
    "GUM": "Guam", "GTM": "Guatemala", "GIN": "Guinea",
    "GNB": "Guinea-Bissau", "GUY": "Guyana", "HTI": "Haiti",
    "VAT": "Vatican City", "HND": "Honduras", "HKG": "Hong Kong",
    "HUN": "Hungary", "ISL": "Iceland", "IND": "India",
    "IDN": "Indonesia", "IRN": "Iran", "IRQ": "Iraq",
    "IRL": "Ireland", "IMY": "Isle of Man", "ISR": "Israel",
    "ITA": "Italy", "JAM": "Jamaica", "JPN": "Japan",
    "JOR": "Jordan", "KAZ": "Kazakhstan", "KEN": "Kenya",
    "KIR": "Kiribati", "PRK": "North Korea", "KOR": "South Korea",
    "KWT": "Kuwait", "KGZ": "Kyrgyzstan", "LAO": "Laos",
    "LVA": "Latvia", "LBN": "Lebanon", "LSO": "Lesotho",
    "LBR": "Liberia", "LBY": "Libya", "LIE": "Liechtenstein",
    "LTU": "Lithuania", "LUX": "Luxembourg", "MAC": "Macao",
    "MKD": "Macedonia", "MDG": "Madagascar", "MWI": "Malawi",
    "MYS": "Malaysia", "MDV": "Maldives", "MLI": "Mali",
    "MLT": "Malta", "MHL": "Marshall Islands", "MTQ": "Martinique",
    "MRT": "Mauritania", "MUS": "Mauritius", "MYT": "Mayotte",
    "MEX": "Mexico", "FSM": "Micronesia", "MDA": "Moldova",
    "MCO": "Monaco", "MNG": "Mongolia", "MTN": "Montenegro",
    "MSR": "Montserrat", "MAR": "Morocco", "MOZ": "Mozambique",
    "MMR": "Myanmar", "NAM": "Namibia", "NRU": "Nauru",
    "NPL": "Nepal", "NLD": "Netherlands", "ANT": "Netherlands Antilles",
    "NCL": "New Caledonia", "NZL": "New Zealand", "NIC": "Nicaragua",
    "NER": "Niger", "NGA": "Nigeria", "NIU": "Niue",
    "NFK": "Norfolk Island", "MNP": "Northern Mariana Islands",
    "NOR": "Norway", "PSE": "Occupied Palestinian Territory",
    "OMN": "Oman", "PAK": "Pakistan", "PLW": "Palau",
    "PAN": "Panama", "PNG": "Papua New Guinea", "PRY": "Paraguay",
    "PER": "Peru", "PHL": "Philippines", "PCN": "Pitcairn",
    "POL": "Poland", "PRT": "Portugal", "PRI": "Puerto Rico",
    "QAT": "Qatar", "REU": "Reunion", "ROM": "Romania",
    "RUS": "Russia", "RWA": "Rwanda", "SHN": "Saint Helena",
    "KNA": "Saint Kitts-Nevis", "LCA": "Saint Lucia",
    "SPM": "Saint Pierre and Miquelon",
    "VCT": "Saint Vincent and the Grenadines",
    "WSM": "Samoa", "SMR": "San Marino", "STP": "Sao Tome and Principe",
    "SAU": "Saudi Arabia", "SEN": "Senegal", "SRB": "Serbia",
    "SYC": "Seychelles", "SLE": "Sierra Leone", "SGP": "Singapore",
    "SVK": "Slovakia", "SVN": "Slovenia", "SLB": "Solomon Islands",
    "SOM": "Somalia", "ZAF": "South Africa", "ESP": "Spain",
    "LKA": "Sri Lanka", "SDN": "Sudan", "SUR": "Suriname",
    "SJM": "Svalbard and Jan Mayen Islands", "SWZ": "Swaziland",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria",
    "TWN": "Taiwan", "TJK": "Tajikistan", "TZA": "Tanzania",
    "THA": "Thailand", "TGO": "Togo", "TKL": "Tokelau",
    "TON": "Tonga", "TTO": "Trinidad and Tobago", "TUN": "Tunisia",
    "TUR": "Turkey", "TKM": "Turkmenistan",
    "TCA": "Turks and Caicos Islands", "TUV": "Tuvalu",
    "UGA": "Uganda", "UKR": "Ukraine", "ARE": "United Arab Emirates",
    "GBR": "United Kingdom", "USA": "United States",
    "VIR": "United States Virgin Islands", "URY": "Uruguay",
    "UZB": "Uzbekistan", "VUT": "Vanuatu", "VEN": "Venezuela",
    "VNM": "Vietnam", "WLF": "Wallis and Futuna Islands",
    "ESH": "Western Sahara", "YEM": "Yemen", "ZMB": "Zambia",
    "ZWE": "Zimbabwe",
}


# =====================================================================
# Official Goldstein Scale (CAMEO.goldsteinscale.txt)
# =====================================================================
# Range: -10.0 (max conflict) to +10.0 (max cooperation)

CAMEO_GOLDSTEIN: Dict[str, float] = {
    "01": 0.0, "010": 0.0, "011": -0.1, "012": -0.4, "013": 0.4,
    "014": 0.0, "015": 0.0, "016": -2.0, "017": 0.0, "018": 3.4, "019": 3.4,
    "02": 3.0, "020": 3.0, "021": 3.4, "0211": 3.4, "0212": 3.4,
    "0213": 3.4, "0214": 3.4, "022": 3.2, "023": 3.4, "0231": 3.4,
    "0232": 3.4, "0233": 3.4, "0234": 3.4, "024": -0.3, "0241": -0.3,
    "0242": -0.3, "0243": -0.3, "0244": -0.3, "025": -0.3, "0251": -0.3,
    "0252": -0.3, "0253": -0.3, "0254": -0.3, "0255": -0.3, "0256": -0.3,
    "026": 4.0, "027": 4.0, "028": 4.0,
    "03": 4.0, "030": 4.0, "031": 5.2, "0311": 5.2, "0312": 5.2,
    "0313": 5.2, "0314": 5.2, "032": 4.5, "033": 5.2, "0331": 5.2,
    "0332": 5.2, "0333": 5.2, "0334": 6.0, "034": 7.0, "0341": 7.0,
    "0342": 7.0, "0343": 7.0, "0344": 7.0, "035": 7.0, "0351": 7.0,
    "0352": 7.0, "0353": 7.0, "0354": 7.0, "0355": 7.0, "0356": 7.0,
    "036": 4.0, "037": 5.0, "038": 7.0, "039": 5.0,
    "04": 1.0, "040": 1.0, "041": 1.0, "042": 1.9, "043": 2.8,
    "044": 2.5, "045": 5.0, "046": 7.0,
    "05": 3.5, "050": 3.5, "051": 3.4, "052": 3.5, "053": 3.8,
    "054": 6.0, "055": 7.0, "056": 7.0, "057": 8.0,
    "06": 6.0, "060": 6.0, "061": 6.4, "062": 7.4, "063": 7.4, "064": 7.0,
    "07": 7.0, "070": 7.0, "071": 7.4, "072": 8.3, "073": 7.4,
    "074": 8.5, "075": 7.0,
    "08": 5.0, "080": 5.0, "081": 5.0, "0811": 5.0, "0812": 5.0,
    "0813": 5.0, "0814": 5.0, "082": 5.0, "083": 5.0, "0831": 5.0,
    "0832": 5.0, "0833": 5.0, "0834": 5.0, "084": 7.0, "0841": 7.0,
    "0842": 7.0, "085": 7.0, "086": 9.0, "0861": 9.0, "0862": 9.0,
    "0863": 9.0, "087": 9.0, "0871": 9.0, "0872": 9.0, "0873": 9.0,
    "0874": 10.0,
    "09": -2.0, "090": -2.0, "091": -2.0, "092": -2.0, "093": -2.0,
    "094": -2.0,
    "10": -5.0, "100": -5.0, "101": -5.0, "1011": -5.0, "1012": -5.0,
    "1013": -5.0, "1014": -5.0, "102": -5.0, "103": -5.0, "1031": -5.0,
    "1032": -5.0, "1033": -5.0, "1034": -5.0, "104": -5.0, "1041": -5.0,
    "1042": -5.0, "1043": -5.0, "1044": -5.0, "105": -5.0, "1051": -5.0,
    "1052": -5.0, "1053": -5.0, "1054": -5.0, "1055": -5.0, "1056": -5.0,
    "107": -5.0, "108": -5.0,
    "11": -2.0, "110": -2.0, "111": -2.0, "112": -2.0, "1121": -2.0,
    "1122": -2.0, "1123": -2.0, "1124": -2.0, "1125": -2.0, "113": -2.0,
    "114": -2.0, "115": -2.0, "116": -2.0,
    "12": -4.0, "120": -4.0, "121": -4.0, "1211": -4.0, "1212": -4.0,
    "122": -4.0, "1221": -4.0, "1222": -4.0, "1223": -4.0, "1224": -4.0,
    "123": -4.0, "1231": -4.0, "1232": -4.0, "1233": -4.0, "1234": -4.0,
    "124": -4.0, "1241": -4.0, "1242": -4.0, "1243": -4.0, "1244": -4.0,
    "1245": -4.0, "1246": -4.0, "125": -5.0, "126": -5.0, "127": -5.0,
    "128": -5.0, "129": -5.0,
    "13": -6.0, "130": -4.4, "131": -5.8, "1311": -5.8, "1312": -5.8,
    "1313": -5.8, "132": -5.8, "1321": -5.8, "1322": -5.8, "1323": -5.8,
    "1324": -5.8, "133": -5.8, "134": -5.8, "135": -5.8, "136": -7.0,
    "137": -7.0, "138": -7.0, "1381": -7.0, "1382": -7.0, "1383": -7.0,
    "1384": -7.0, "1385": -7.0, "139": -7.0,
    "14": -6.5, "140": -6.5, "141": -6.5, "1411": -6.5, "1412": -6.5,
    "1413": -6.5, "1414": -6.5, "142": -6.5, "1421": -6.5, "1422": -6.5,
    "1423": -6.5, "1424": -6.5, "143": -6.5, "1431": -6.5, "1432": -6.5,
    "1433": -6.5, "1434": -6.5, "144": -7.5, "1441": -7.5, "1442": -7.5,
    "1443": -7.5, "1444": -7.5, "145": -7.5, "1451": -7.5, "1452": -7.5,
    "1453": -7.5, "1454": -7.5,
    "15": -7.2, "150": -7.2, "151": -7.2, "152": -7.2, "153": -7.2,
    "154": -7.2,
    "16": -4.0, "160": -4.0, "161": -4.0, "162": -5.6, "1621": -5.6,
    "1622": -5.6, "1623": -5.6, "163": -8.0, "164": -7.0, "165": -6.5,
    "166": -7.0, "1661": -7.0, "1662": -7.0, "1663": -7.0,
    "17": -7.0, "170": -7.0, "171": -9.2, "1711": -9.2, "1712": -9.2,
    "172": -5.0, "1721": -5.0, "1722": -5.0, "1723": -5.0, "1724": -5.0,
    "173": -5.0, "174": -5.0, "175": -9.0,
    "18": -9.0, "180": -9.0, "181": -9.0, "182": -9.5, "1821": -9.0,
    "1822": -9.0, "1823": -10.0, "183": -10.0, "1831": -10.0,
    "1832": -10.0, "1833": -10.0, "184": -8.0, "185": -8.0, "186": -10.0,
    "19": -10.0, "190": -10.0, "191": -9.5, "192": -9.5, "193": -10.0,
    "194": -10.0, "195": -10.0, "196": -9.5,
    "20": -10.0, "200": -10.0, "201": -9.5, "202": -10.0, "203": -10.0,
    "204": -10.0, "2041": -10.0, "2042": -10.0,
}


# =====================================================================
# Event Codes (CAMEO.eventcodes.txt) — root and sub-codes
# =====================================================================

CAMEO_EVENT_ROOT_CODES: Dict[str, str] = {
    "01": "MAKE PUBLIC STATEMENT",
    "02": "APPEAL",
    "03": "EXPRESS INTENT TO COOPERATE",
    "04": "CONSULT",
    "05": "ENGAGE IN DIPLOMATIC COOPERATION",
    "06": "ENGAGE IN MATERIAL COOPERATION",
    "07": "PROVIDE AID",
    "08": "YIELD",
    "09": "INVESTIGATE",
    "10": "DEMAND",
    "11": "DISAPPROVE",
    "12": "REJECT",
    "13": "THREATEN",
    "14": "PROTEST",
    "15": "EXHIBIT FORCE POSTURE",
    "16": "REDUCE RELATIONS",
    "17": "COERCE",
    "18": "ASSAULT",
    "19": "FIGHT",
    "20": "USE UNCONVENTIONAL MASS VIOLENCE",
}

# Full event codes (selected high-impact sub-codes for signal enrichment)
CAMEO_EVENT_CODES: Dict[str, str] = {
    # 01 — Public Statement
    "010": "Make statement, not specified below",
    "011": "Decline comment",
    "012": "Make pessimistic comment",
    "013": "Make optimistic comment",
    "014": "Consider policy option",
    "015": "Acknowledge or claim responsibility",
    "016": "Deny responsibility",
    "017": "Engage in symbolic act",
    "018": "Make empathetic comment",
    "019": "Express accord",
    # 04 — Consult
    "040": "Consult, not specified below",
    "041": "Discuss by telephone",
    "042": "Make a visit",
    "043": "Host a visit",
    "045": "Mediate",
    "046": "Engage in negotiation",
    # 05 — Diplomatic Cooperation
    "050": "Engage in diplomatic cooperation",
    "051": "Praise or endorse",
    "052": "Defend verbally",
    "053": "Rally support on behalf of",
    "054": "Grant diplomatic recognition",
    "055": "Apologize",
    "056": "Forgive",
    "057": "Sign formal agreement",
    # 06 — Material Cooperation
    "060": "Engage in material cooperation",
    "061": "Cooperate economically",
    "062": "Cooperate militarily",
    "063": "Engage in judicial cooperation",
    "064": "Share intelligence or information",
    # 07 — Provide Aid
    "071": "Provide economic aid",
    "072": "Provide military aid",
    "073": "Provide humanitarian aid",
    "074": "Provide military protection or peacekeeping",
    # 08 — Yield
    "0871": "Declare truce, ceasefire",
    "0872": "Ease military blockade",
    "0873": "Demobilize armed forces",
    "0874": "Retreat or surrender militarily",
    # 10 — Demand
    "100": "Demand, not specified below",
    "101": "Demand information, investigation",
    "102": "Demand policy support",
    "104": "Demand political reform",
    "107": "Demand ceasefire",
    "108": "Demand meeting, negotiation",
    # 11 — Disapprove
    "110": "Disapprove, not specified below",
    "111": "Criticize or denounce",
    "112": "Accuse",
    "1121": "Accuse of crime, corruption",
    "1122": "Accuse of human rights abuses",
    "1123": "Accuse of aggression",
    "1124": "Accuse of war crimes",
    "1125": "Accuse of espionage, treason",
    "113": "Rally opposition against",
    "114": "Complain officially",
    "115": "Bring lawsuit against",
    # 12 — Reject
    "1212": "Reject military cooperation",
    "1222": "Reject request for military aid",
    "1246": "Refuse to de-escalate military engagement",
    "125": "Reject proposal to meet, discuss, or negotiate",
    "128": "Defy norms, law",
    "129": "Veto",
    # 13 — Threaten
    "130": "Threaten, not specified below",
    "131": "Threaten non-force",
    "1311": "Threaten to reduce or stop aid",
    "1312": "Threaten to boycott, embargo, or sanction",
    "1313": "Threaten to reduce or break relations",
    "133": "Threaten political dissent, protest",
    "136": "Threaten to halt international involvement",
    "137": "Threaten with violent repression",
    "138": "Threaten to use military force",
    "1381": "Threaten blockade",
    "1382": "Threaten occupation",
    "1383": "Threaten unconventional violence",
    "1384": "Threaten conventional attack",
    "1385": "Threaten attack with WMD",
    "139": "Give ultimatum",
    # 14 — Protest
    "140": "Engage in political dissent",
    "141": "Demonstrate or rally",
    "143": "Conduct strike or boycott",
    "144": "Obstruct passage, block",
    "145": "Protest violently, riot",
    "1451": "Violent protest for leadership change",
    "1452": "Violent protest for policy change",
    "1453": "Violent protest for rights",
    # 15 — Force Posture
    "150": "Demonstrate military or police power",
    "151": "Increase police alert status",
    "152": "Increase military alert status",
    "153": "Mobilize or increase police power",
    "154": "Mobilize or increase armed forces",
    # 16 — Reduce Relations
    "160": "Reduce relations, not specified below",
    "161": "Reduce or break diplomatic relations",
    "162": "Reduce or stop aid",
    "163": "Impose embargo, boycott, or sanctions",
    "164": "Halt negotiations",
    "165": "Halt mediation",
    "166": "Expel or withdraw",
    "1661": "Expel or withdraw peacekeepers",
    "1662": "Expel or withdraw inspectors",
    # 17 — Coerce
    "170": "Coerce, not specified below",
    "171": "Seize or damage property",
    "1711": "Confiscate property",
    "1712": "Destroy property",
    "172": "Impose administrative sanctions",
    "1721": "Impose restrictions on political freedoms",
    "1724": "Impose state of emergency or martial law",
    "173": "Arrest, detain, or charge with legal action",
    "174": "Expel or deport individuals",
    "175": "Use tactics of violent repression",
    # 18 — Assault
    "180": "Use unconventional violence",
    "181": "Abduct, hijack, or take hostage",
    "182": "Physically assault",
    "1821": "Sexually assault",
    "1822": "Torture",
    "1823": "Kill by physical assault",
    "183": "Conduct bombing",
    "1831": "Carry out suicide bombing",
    "1832": "Carry out car bombing",
    "1833": "Carry out roadside bombing",
    "184": "Use as human shield",
    "185": "Attempt to assassinate",
    "186": "Assassinate",
    # 19 — Fight
    "190": "Use conventional military force",
    "191": "Impose blockade, restrict movement",
    "192": "Occupy territory",
    "193": "Fight with small arms and light weapons",
    "194": "Fight with artillery and tanks",
    "195": "Employ aerial weapons",
    "196": "Violate ceasefire",
    # 20 — Mass Violence
    "200": "Use unconventional mass violence",
    "201": "Engage in mass expulsion",
    "202": "Engage in mass killings",
    "203": "Engage in ethnic cleansing",
    "204": "Use weapons of mass destruction",
    "2041": "Use chemical, biological, or radiological weapons",
    "2042": "Detonate nuclear weapons",
}


# =====================================================================
# Actor Type Codes (CAMEO.type.txt)
# =====================================================================

CAMEO_ACTOR_TYPES: Dict[str, str] = {
    # ── State / Security actors ───────────────────────────────────
    "COP": "Police forces",
    "GOV": "Government",
    "JUD": "Judiciary",
    "MIL": "Military",
    "SPY": "State Intelligence",
    # ── Armed non-state ───────────────────────────────────────────
    "INS": "Insurgents",
    "REB": "Rebels",
    "SEP": "Separatist Rebels",
    "UAF": "Unaligned Armed Forces",
    # ── Opposition ────────────────────────────────────────────────
    "OPP": "Political Opposition",
    "MOD": "Moderate",
    "RAD": "Radical",
    # ── Civil society ─────────────────────────────────────────────
    "AGR": "Agriculture",
    "BUS": "Business",
    "CRM": "Criminal",
    "CVL": "Civilian",
    "DEV": "Development",
    "EDU": "Education",
    "ELI": "Elites",
    "ENV": "Environmental",
    "HLH": "Health",
    "HRI": "Human Rights",
    "LAB": "Labor",
    "LEG": "Legislature",
    "MED": "Media",
    "REF": "Refugees",
    "SET": "Settler",
    # ── International ─────────────────────────────────────────────
    "AMN": "Amnesty International",
    "IRC": "Red Cross",
    "GRP": "Greenpeace",
    "UNO": "United Nations",
    "PKO": "Peacekeepers",
    "IGO": "Inter-Governmental Organization",
    "IMG": "International Militarized Group",
    "INT": "International/Transnational Generic",
    "MNC": "Multinational Corporation",
    "NGM": "Non-Governmental Movement",
    "NGO": "Non-Governmental Organization",
    "UIS": "Unidentified State Actor",
}

# ── Actor type classification sets (for signal boosting) ──────────

# Military / security actors → boost escalation signals
MILITARY_ACTOR_TYPES: Set[str] = {"MIL", "SPY", "COP", "UAF"}

# Armed non-state actors → boost insurgency / instability signals
ARMED_NONSTATE_TYPES: Set[str] = {"INS", "REB", "SEP", "IMG"}

# Government actors → boost diplomatic / coercive signals
GOVERNMENT_ACTOR_TYPES: Set[str] = {"GOV", "JUD", "LEG", "ELI"}

# International actors → boost credibility
INTERNATIONAL_ACTOR_TYPES: Set[str] = {"UNO", "PKO", "IGO", "AMN", "IRC"}


# =====================================================================
# Religion Codes (CAMEO.religion.txt)
# =====================================================================

CAMEO_RELIGIONS: Dict[str, str] = {
    "ADR": "African Diasporic Religion",
    "ALE": "Alewi",
    "ATH": "Agnostic",
    "BAH": "Bahai Faith",
    "BUD": "Buddhism",
    "CHR": "Christianity",
    "CON": "Confucianism",
    "CPT": "Coptic",
    "CTH": "Catholic",
    "DOX": "Orthodox",
    "DRZ": "Druze",
    "HIN": "Hinduism",
    "HSD": "Hasidic",
    "ITR": "Indigenous Tribal Religion",
    "JAN": "Jainism",
    "JEW": "Judaism",
    "JHW": "Jehovah's Witness",
    "LDS": "Latter Day Saints",
    "MOS": "Muslim",
    "MRN": "Maronite",
    "NRM": "New Religious Movement",
    "PAG": "Pagan",
    "PRO": "Protestant",
    "SFI": "Sufi",
    "SHI": "Shia",
    "SHN": "Old Shinto School",
    "SIK": "Sikh",
    "SUN": "Sunni",
    "TAO": "Taoist",
    "UDX": "Ultra-Orthodox",
    "ZRO": "Zoroastrianism",
}


# =====================================================================
# Quad Class labels
# =====================================================================

CAMEO_QUAD_CLASS: Dict[str, str] = {
    "1": "Verbal Cooperation",
    "2": "Material Cooperation",
    "3": "Verbal Conflict",
    "4": "Material Conflict",
}


__all__ = [
    "CAMEO_COUNTRY_CODES",
    "CAMEO_REGIONAL_CODES",
    "CAMEO_GOLDSTEIN",
    "CAMEO_EVENT_ROOT_CODES",
    "CAMEO_EVENT_CODES",
    "CAMEO_ACTOR_TYPES",
    "CAMEO_RELIGIONS",
    "CAMEO_QUAD_CLASS",
    "MILITARY_ACTOR_TYPES",
    "ARMED_NONSTATE_TYPES",
    "GOVERNMENT_ACTOR_TYPES",
    "INTERNATIONAL_ACTOR_TYPES",
]
