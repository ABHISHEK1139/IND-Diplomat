"""
World Model API
================
The central brain of DIP 3.0. Replaces raw text reading with a structured,
persisted knowledge graph. Downstream reasoning agents query this API
to understand Entities, Claims, Contradictions, and Timelines.
"""

import logging
from typing import List, Dict, Any

from dip.pipeline.world_model.world.graph.neo4j_sync import Neo4jSync

logger = logging.getLogger("Layer3.WorldModel")


class WorldModel:
    """
    The unified interface for the Dynamic World Model.
    Wraps the Neo4j Graph and Qdrant Vector stores.
    """

    def __init__(self):
        self.graph = Neo4jSync()

    def get_beliefs_about(self, entity_name: str, max_hops: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieves the known subgraph for a specific entity.
        Returns the relationships and claims associated with it.
        """
        if not self.graph.connect():
            logger.warning("Graph database disconnected. Returning empty beliefs.")
            return []
            
        return self.graph.get_subgraph(entity_name, hops=max_hops)

    def register_claim(self, subject: str, predicate: str, object_: str, evidence_id: str, confidence: float):
        """
        Registers a new claim into the World Model.
        """
        # Ensure entities exist
        self.graph.merge_entity(subject)
        self.graph.merge_entity(object_)
        
        # Link them
        self.graph.merge_relationship(subject, predicate, object_)
        
        # In a full implementation, we'd also link the evidence_id as a node
        # pointing to the relationship, creating a hypergraph or reified relationship.
        logger.info(f"Registered claim: {subject} -> {predicate} -> {object_}")

    def get_contradictions(self) -> List[Dict[str, Any]]:
        """
        Returns all unresolved contradictions in the World Model.
        (Mock implementation for now)
        """
        # In a real system, we'd query Neo4j for [c:Claim {contradicted: true}]
        return []

    def get_unknowns(self) -> List[str]:
        """
        Returns gaps in the knowledge graph based on the active investigation.
        """
        return []

    def get_timeline(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves time-sequenced events for an entity.
        """
        return []
