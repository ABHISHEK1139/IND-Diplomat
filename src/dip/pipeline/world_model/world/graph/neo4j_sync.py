"""
Neo4j Graph Synchronization
============================
Connects to Neo4j to store and retrieve the persistent World Model
graph (Entities and their Relationships).
"""

import logging
import os
from typing import List, Dict, Any

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

logger = logging.getLogger("Layer3.Neo4jSync")


class Neo4jSync:
    """
    Manages the connection and Cypher queries to Neo4j for the World Model.
    """

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None

    def connect(self) -> bool:
        """Establish connection to Neo4j."""
        if not GraphDatabase:
            logger.warning("neo4j library not installed. Graph sync disabled.")
            return False
            
        if self.driver:
            return True

        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Verify connection
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.driver = None
            return False

    def close(self):
        """Close the database driver."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed.")

    def merge_entity(self, name: str, label: str = "Entity", properties: dict = None) -> bool:
        """
        Merges an entity node into the graph (creates if not exists, updates if exists).
        """
        if not self.connect():
            return False
            
        props = properties or {}
        query = f"""
        MERGE (n:{label} {{name: $name}})
        SET n += $props
        RETURN n
        """
        
        try:
            with self.driver.session() as session:
                session.run(query, name=name, props=props)
            return True
        except Exception as e:
            logger.error(f"Failed to merge entity '{name}': {e}")
            return False

    def merge_relationship(self, head: str, relation: str, tail: str) -> bool:
        """
        Creates a relationship between two entities.
        """
        if not self.connect():
            return False
            
        # Clean relation string to be a valid Neo4j relationship type
        rel_type = relation.upper().replace(" ", "_").replace("-", "_")
        if not rel_type:
            return False
            
        query = f"""
        MERGE (h:Entity {{name: $head}})
        MERGE (t:Entity {{name: $tail}})
        MERGE (h)-[r:{rel_type}]->(t)
        RETURN r
        """
        
        try:
            with self.driver.session() as session:
                session.run(query, head=head, tail=tail)
            return True
        except Exception as e:
            logger.error(f"Failed to merge relationship '{head} -> {relation} -> {tail}': {e}")
            return False

    def get_subgraph(self, center_entity: str, hops: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieves the neighborhood of an entity for reasoning layers.
        """
        if not self.connect():
            return []
            
        # Flexible length path matching
        query = f"""
        MATCH p=(n:Entity {{name: $name}})-[*1..{hops}]-(m)
        RETURN relationships(p) as rels, nodes(p) as nodes
        LIMIT 100
        """
        
        results = []
        try:
            with self.driver.session() as session:
                records = session.run(query, name=center_entity)
                for record in records:
                    # Simplify output for prompt context
                    rels = record["rels"]
                    for rel in rels:
                        results.append({
                            "head": rel.nodes[0]["name"],
                            "type": rel.type,
                            "tail": rel.nodes[1]["name"]
                        })
            return results
        except Exception as e:
            logger.error(f"Failed to get subgraph for '{center_entity}': {e}")
            return []
