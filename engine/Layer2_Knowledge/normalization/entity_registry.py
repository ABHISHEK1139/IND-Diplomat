"""
Entity Registry - Canonical Actor Resolution
===============================================
Resolves messy real-world names into canonical IDs.

Without this:
    "USA" != "United States" != "US" != "America"
    → Graph has 4 separate nodes for same country
    → False causal links everywhere

With this:
    All resolve to canonical_id = "USA"

Also knows:
    - Actor types (state, IGO, militia, corporation)
    - Parent relationships (France is member_of EU, but EU != France)
    - 3-char ISO codes ↔ 2-char ISO codes ↔ CAMEO codes ↔ common names
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger("entity_registry")


# =====================================================================
# Actor Types
# =====================================================================

class ActorType(Enum):
    """Classification of geopolitical actors."""
    STATE             = "state"              # Sovereign nation
    IGO               = "igo"                # Intergovernmental org (UN, EU, NATO)
    NGO               = "ngo"                # Non-governmental org
    MILITIA           = "militia"            # Armed non-state actor
    CORPORATION       = "corporation"        # Major corporation
    POLITICAL_PARTY   = "political_party"
    REBEL_GROUP       = "rebel_group"
    TERRORIST_ORG     = "terrorist_org"
    INDIVIDUAL        = "individual"         # Head of state, key figure
    UNKNOWN           = "unknown"


# =====================================================================
# Entity Record
# =====================================================================

@dataclass
class EntityRecord:
    """A canonical entity with all its aliases."""
    canonical_id: str                         # "USA", "IND", "NATO"
    canonical_name: str                       # "United States of America"
    actor_type: ActorType
    aliases: Set[str] = field(default_factory=set)
    iso2: str = ""                            # "US", "IN"
    iso3: str = ""                            # "USA", "IND"
    cameo_code: str = ""                      # GDELT CAMEO code
    parent_orgs: List[str] = field(default_factory=list)   # ["NATO", "QUAD"]
    region: str = ""                          # "South Asia", "Europe"
    properties: Dict = field(default_factory=dict)


# =====================================================================
# Entity Registry
# =====================================================================

class EntityRegistry:
    """
    Resolves any name/code to a canonical entity.

    Lookup is case-insensitive.
    All aliases are registered at init time.
    """

    def __init__(self):
        self._entities: Dict[str, EntityRecord] = {}   # canonical_id → EntityRecord
        self._alias_map: Dict[str, str] = {}           # lowercase alias → canonical_id
        self._load_default_entities()

    def register(self, entity: EntityRecord) -> None:
        """Register an entity and all its aliases."""
        cid = entity.canonical_id.upper()
        entity.canonical_id = cid
        self._entities[cid] = entity

        # Register all aliases (case-insensitive)
        all_names = {cid, entity.canonical_name, entity.iso2, entity.iso3, entity.cameo_code}
        all_names.update(entity.aliases)

        for name in all_names:
            if name:
                self._alias_map[name.lower()] = cid

    def resolve(self, name: str) -> Optional[str]:
        """
        Resolve any name/alias to a canonical ID.

        Returns None if the name is completely unknown.
        """
        if not name:
            return None
        return self._alias_map.get(name.strip().lower())

    def resolve_or_keep(self, name: str) -> str:
        """Resolve if known, otherwise return the input unchanged."""
        return self.resolve(name) or name

    def get_entity(self, canonical_id: str) -> Optional[EntityRecord]:
        """Get the full entity record for a canonical ID."""
        return self._entities.get(canonical_id.upper())

    def is_state(self, name: str) -> bool:
        """Check if the resolved entity is a sovereign state."""
        cid = self.resolve(name)
        if cid:
            entity = self._entities.get(cid)
            return entity and entity.actor_type == ActorType.STATE
        return False

    def is_igo(self, name: str) -> bool:
        """Check if the resolved entity is an intergovernmental org."""
        cid = self.resolve(name)
        if cid:
            entity = self._entities.get(cid)
            return entity and entity.actor_type == ActorType.IGO
        return False

    def get_members(self, org_id: str) -> List[str]:
        """Get all states that list org_id as a parent org."""
        org = org_id.upper()
        return [
            cid for cid, entity in self._entities.items()
            if org in entity.parent_orgs and entity.actor_type == ActorType.STATE
        ]

    def normalize_actors(self, actors: List[str]) -> List[str]:
        """Normalize a list of actor names to canonical IDs."""
        return [self.resolve_or_keep(a) for a in actors if a]

    # ─────────────────────────────────────────────────────────────
    # Default Entities (the ones our system cares about most)
    # ─────────────────────────────────────────────────────────────

    def _load_default_entities(self):
        """Load the core set of entities the system needs to know about."""

        states = [
            # South Asia (Primary focus)
            EntityRecord("IND", "India", ActorType.STATE,
                         {"india", "bharat", "republic of india", "hindustan"},
                         iso2="IN", iso3="IND", cameo_code="IND",
                         parent_orgs=["QUAD", "BRICS", "SCO", "G20"],
                         region="South Asia"),
            EntityRecord("PAK", "Pakistan", ActorType.STATE,
                         {"pakistan", "islamic republic of pakistan"},
                         iso2="PK", iso3="PAK", cameo_code="PAK",
                         parent_orgs=["OIC", "SCO"],
                         region="South Asia"),
            EntityRecord("BGD", "Bangladesh", ActorType.STATE,
                         {"bangladesh"},
                         iso2="BD", iso3="BGD", cameo_code="BGD",
                         region="South Asia"),
            EntityRecord("LKA", "Sri Lanka", ActorType.STATE,
                         {"sri lanka", "ceylon"},
                         iso2="LK", iso3="LKA", cameo_code="LKA",
                         region="South Asia"),
            EntityRecord("NPL", "Nepal", ActorType.STATE,
                         {"nepal"},
                         iso2="NP", iso3="NPL", cameo_code="NPL",
                         region="South Asia"),

            # Major powers
            EntityRecord("USA", "United States of America", ActorType.STATE,
                         {"usa", "united states", "us", "america", "u.s.", "u.s.a.",
                          "united states of america", "the united states"},
                         iso2="US", iso3="USA", cameo_code="USA",
                         parent_orgs=["NATO", "QUAD", "G7", "G20", "AUKUS"],
                         region="North America"),
            EntityRecord("CHN", "China", ActorType.STATE,
                         {"china", "prc", "people's republic of china",
                          "peoples republic of china", "mainland china"},
                         iso2="CN", iso3="CHN", cameo_code="CHN",
                         parent_orgs=["BRICS", "SCO", "G20"],
                         region="East Asia"),
            EntityRecord("RUS", "Russia", ActorType.STATE,
                         {"russia", "russian federation", "rf", "moscow"},
                         iso2="RU", iso3="RUS", cameo_code="RUS",
                         parent_orgs=["BRICS", "SCO", "G20"],
                         region="Europe/Asia"),
            EntityRecord("GBR", "United Kingdom", ActorType.STATE,
                         {"uk", "united kingdom", "britain", "great britain",
                          "england", "gbr", "aukus"},
                         iso2="GB", iso3="GBR", cameo_code="GBR",
                         parent_orgs=["NATO", "G7", "G20", "AUKUS"],
                         region="Europe"),
            EntityRecord("FRA", "France", ActorType.STATE,
                         {"france", "french republic"},
                         iso2="FR", iso3="FRA", cameo_code="FRA",
                         parent_orgs=["NATO", "EU", "G7", "G20"],
                         region="Europe"),
            EntityRecord("DEU", "Germany", ActorType.STATE,
                         {"germany", "federal republic of germany", "deutschland"},
                         iso2="DE", iso3="DEU", cameo_code="DEU",
                         parent_orgs=["NATO", "EU", "G7", "G20"],
                         region="Europe"),

            # Middle East / Central Asia
            EntityRecord("IRN", "Iran", ActorType.STATE,
                         {"iran", "islamic republic of iran", "persia"},
                         iso2="IR", iso3="IRN", cameo_code="IRN",
                         parent_orgs=["BRICS", "OIC", "SCO"],
                         region="Middle East"),
            EntityRecord("SAU", "Saudi Arabia", ActorType.STATE,
                         {"saudi arabia", "saudi", "ksa", "kingdom of saudi arabia"},
                         iso2="SA", iso3="SAU", cameo_code="SAU",
                         parent_orgs=["OIC", "OPEC", "G20"],
                         region="Middle East"),
            EntityRecord("ISR", "Israel", ActorType.STATE,
                         {"israel", "state of israel"},
                         iso2="IL", iso3="ISR", cameo_code="ISR",
                         region="Middle East"),
            EntityRecord("TUR", "Turkey", ActorType.STATE,
                         {"turkey", "turkiye", "republic of turkey", "republic of turkiye"},
                         iso2="TR", iso3="TUR", cameo_code="TUR",
                         parent_orgs=["NATO", "G20", "OIC"],
                         region="Middle East/Europe"),
            EntityRecord("AFG", "Afghanistan", ActorType.STATE,
                         {"afghanistan", "islamic emirate of afghanistan"},
                         iso2="AF", iso3="AFG", cameo_code="AFG",
                         parent_orgs=["OIC"],
                         region="South Asia"),

            # East Asia / Pacific
            EntityRecord("JPN", "Japan", ActorType.STATE,
                         {"japan", "nippon"},
                         iso2="JP", iso3="JPN", cameo_code="JPN",
                         parent_orgs=["QUAD", "G7", "G20"],
                         region="East Asia"),
            EntityRecord("KOR", "South Korea", ActorType.STATE,
                         {"south korea", "republic of korea", "rok", "korea"},
                         iso2="KR", iso3="KOR", cameo_code="KOR",
                         parent_orgs=["G20"],
                         region="East Asia"),
            EntityRecord("PRK", "North Korea", ActorType.STATE,
                         {"north korea", "dprk", "democratic people's republic of korea"},
                         iso2="KP", iso3="PRK", cameo_code="PRK",
                         region="East Asia"),
            EntityRecord("TWN", "Taiwan", ActorType.STATE,
                         {"taiwan", "republic of china", "roc", "chinese taipei"},
                         iso2="TW", iso3="TWN", cameo_code="TWN",
                         region="East Asia"),
            EntityRecord("AUS", "Australia", ActorType.STATE,
                         {"australia"},
                         iso2="AU", iso3="AUS", cameo_code="AUS",
                         parent_orgs=["QUAD", "AUKUS", "G20"],
                         region="Oceania"),

            # Africa
            EntityRecord("ZAF", "South Africa", ActorType.STATE,
                         {"south africa", "rsa"},
                         iso2="ZA", iso3="ZAF", cameo_code="ZAF",
                         parent_orgs=["BRICS", "G20"],
                         region="Africa"),

            # Europe
            EntityRecord("UKR", "Ukraine", ActorType.STATE,
                         {"ukraine"},
                         iso2="UA", iso3="UKR", cameo_code="UKR",
                         region="Europe"),
            EntityRecord("POL", "Poland", ActorType.STATE,
                         {"poland", "republic of poland"},
                         iso2="PL", iso3="POL", cameo_code="POL",
                         parent_orgs=["NATO", "EU"],
                         region="Europe"),

            # Americas
            EntityRecord("BRA", "Brazil", ActorType.STATE,
                         {"brazil", "brasil"},
                         iso2="BR", iso3="BRA", cameo_code="BRA",
                         parent_orgs=["BRICS", "G20"],
                         region="South America"),
            EntityRecord("CAN", "Canada", ActorType.STATE,
                         {"canada"},
                         iso2="CA", iso3="CAN", cameo_code="CAN",
                         parent_orgs=["NATO", "G7", "G20"],
                         region="North America"),
        ]

        igos = [
            EntityRecord("NATO", "North Atlantic Treaty Organization", ActorType.IGO,
                         {"nato", "north atlantic treaty organization", "atlantic alliance"},
                         region="Transatlantic"),
            EntityRecord("EU", "European Union", ActorType.IGO,
                         {"eu", "european union", "europe"},
                         region="Europe"),
            EntityRecord("UN", "United Nations", ActorType.IGO,
                         {"un", "united nations"},
                         region="Global"),
            EntityRecord("BRICS", "BRICS", ActorType.IGO,
                         {"brics"},
                         region="Global"),
            EntityRecord("SCO", "Shanghai Cooperation Organisation", ActorType.IGO,
                         {"sco", "shanghai cooperation organisation",
                          "shanghai cooperation organization"},
                         region="Eurasia"),
            EntityRecord("QUAD", "Quadrilateral Security Dialogue", ActorType.IGO,
                         {"quad", "the quad", "quadrilateral security dialogue"},
                         region="Indo-Pacific"),
            EntityRecord("AUKUS", "AUKUS", ActorType.IGO,
                         {"aukus"},
                         region="Indo-Pacific"),
            EntityRecord("ASEAN", "Association of Southeast Asian Nations", ActorType.IGO,
                         {"asean"},
                         region="Southeast Asia"),
            EntityRecord("OIC", "Organisation of Islamic Cooperation", ActorType.IGO,
                         {"oic", "organisation of islamic cooperation"},
                         region="Islamic World"),
            EntityRecord("OPEC", "Organization of Petroleum Exporting Countries", ActorType.IGO,
                         {"opec"},
                         region="Global"),
            EntityRecord("G7", "Group of Seven", ActorType.IGO,
                         {"g7", "group of seven", "g-7"},
                         region="Global"),
            EntityRecord("G20", "Group of Twenty", ActorType.IGO,
                         {"g20", "group of twenty", "g-20"},
                         region="Global"),
        ]

        for entity in states + igos:
            self.register(entity)

        logger.info(
            f"Entity registry loaded: {len(self._entities)} entities, "
            f"{len(self._alias_map)} aliases"
        )


# =====================================================================
# Module-Level Singleton
# =====================================================================

entity_registry = EntityRegistry()


__all__ = [
    "EntityRegistry",
    "EntityRecord",
    "ActorType",
    "entity_registry",
]
