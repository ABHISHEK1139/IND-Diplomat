"""
Entity Registry (Layer 2)
=========================
Tracks entities and their relationships.
"""

from typing import Dict, List, Tuple

class EntityRegistry:
    def __init__(self):
        self.entities = {}
        self.relationships = {}

    def register_entity(self, code: str, name: str, type_: str = "STATE"):
        self.entities[code] = {"name": name, "type": type_}

    def set_relationship(self, entity1: str, entity2: str, relation: str):
        # normalize to alphabetical order
        pair = tuple(sorted([entity1, entity2]))
        self.relationships[pair] = relation

    def get_relationship(self, entity1: str, entity2: str) -> str:
        pair = tuple(sorted([entity1, entity2]))
        return self.relationships.get(pair, "NEUTRAL")
