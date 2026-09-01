
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import os
import time
from typing import List, Dict, Any, Optional


# ══════════════════════════════════════════════════════════════════
# Pre-Defined Geopolitical Relationship Types
# ══════════════════════════════════════════════════════════════════
# These are the ONLY relationship types the system uses.
# Every edge in the graph must be one of these.

GEOPOLITICAL_RELATIONSHIPS = {
    # Alliance & Partnership
    "ALLY_OF":            {"category": "alliance",   "directed": False, "description": "Formal/informal military alliance"},
    "MEMBER_OF":          {"category": "membership", "directed": True,  "description": "Entity is a member of an organization"},
    "PARTNER_OF":         {"category": "alliance",   "directed": False, "description": "Strategic or economic partner"},

    # Conflict
    "CONFLICT_WITH":      {"category": "conflict",   "directed": False, "description": "Active or frozen armed conflict"},
    "BORDER_DISPUTE":     {"category": "conflict",   "directed": False, "description": "Territorial/border dispute"},
    "RIVALS_WITH":        {"category": "conflict",   "directed": False, "description": "Strategic rivalry without open conflict"},

    # Coercion
    "SANCTIONED_BY":      {"category": "coercion",   "directed": True,  "description": "Under sanctions imposed by"},
    "BLOCKADED_BY":       {"category": "coercion",   "directed": True,  "description": "Under trade/naval blockade by"},
    "PRESSURED_BY":       {"category": "coercion",   "directed": True,  "description": "Under diplomatic/economic pressure by"},

    # Economic
    "TRADE_DEPENDENT_ON": {"category": "economic",   "directed": True,  "description": "Trade dependency (import reliance)"},
    "TRADE_PARTNER":      {"category": "economic",   "directed": False, "description": "Significant bilateral trade"},
    "AID_RECIPIENT_OF":   {"category": "economic",   "directed": True,  "description": "Receives development/military aid from"},
    "ARMS_SUPPLIER_TO":   {"category": "economic",   "directed": True,  "description": "Supplies weapons/defense equipment to"},

    # Diplomatic
    "MEDIATOR_OF":        {"category": "diplomatic", "directed": True,  "description": "Mediates between parties"},
    "GUARANTOR_OF":       {"category": "diplomatic", "directed": True,  "description": "Guarantor of treaty/agreement"},
    "RECOGNIZED_BY":      {"category": "diplomatic", "directed": True,  "description": "Diplomatically recognized by"},

    # Legal / Treaty
    "SIGNATORY_TO":       {"category": "legal",      "directed": True,  "description": "Signatory to a treaty/agreement"},
    "BOUND_BY":           {"category": "legal",      "directed": True,  "description": "Legally bound by resolution/ruling"},

    # Intelligence / Proxy
    "PROXY_OF":           {"category": "proxy",      "directed": True,  "description": "Acts as proxy/proxy warfare agent for"},
    "SUPPORTS":           {"category": "proxy",      "directed": True,  "description": "Provides support to (non-state actor)"},
}

VALID_RELATIONSHIP_TYPES = set(GEOPOLITICAL_RELATIONSHIPS.keys())


class GraphManager:
    """
    Production-grade Graph Manager with:
    1. Connection retry logic
    2. Graceful degradation if Neo4j unavailable
    3. Hierarchical Indexing
    4. Temporal Ledger (DEU)
    5. Community Detection (Leiden)
    """
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.driver = None
        self._connected = False
        
        self._connect()
    
    def _connect(self):
        """Attempts to connect to Neo4j with retry logic."""
        for attempt in range(self.max_retries):
            try:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                # Verify connection
                with self.driver.session() as session:
                    session.run("RETURN 1")
                self._connected = True
                print(f"[GraphManager] Connected to Neo4j at {self.uri}")
                return
            except (ServiceUnavailable, AuthError) as e:
                print(f"[GraphManager] Connection attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
            except Exception as e:
                print(f"[GraphManager] Unexpected error: {e}")
                break
        
        print("[GraphManager] WARNING: Running in degraded mode (no Neo4j connection)")
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected

    def close(self):
        if self.driver:
            self.driver.close()

    def init_schema(self):
        """
        Initializes graph schema with:
        - Hierarchical Indexing: Jurisdiction -> Treaty -> Article -> ComponentID
        - Temporal Ledger indexes
        """
        if not self._connected:
            print("[GraphManager] Skipping schema init (no connection)")
            return
        
        queries = [
            # Hierarchical Indexing
            "CREATE CONSTRAINT IF NOT EXISTS FOR (j:Jurisdiction) REQUIRE j.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Treaty) REQUIRE t.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (c:Component) ON (c.id)",
            
            # Temporal Ledger
            "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.start_date, e.end_date)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Treaty) ON (t.signed_date)"
        ]
        
        with self.driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    print(f"[GraphManager] Schema query failed: {e}")
        
        print("[GraphManager] Schema initialized with Hierarchical Indexing and Temporal Ledgers.")

    def run_community_detection(self):
        """
        Implements Leiden Technique for 'Geopolitical Communities'.
        Requires Neo4j Graph Data Science plugin.
        """
        if not self._connected:
            print("[GraphManager] Skipping community detection (no connection)")
            return
        
        cypher = """
        CALL gds.leiden.write({
            nodeProjection: 'Entity',
            relationshipProjection: 'RELATED_TO',
            writeProperty: 'communityId'
        })
        """
        try:
            with self.driver.session() as session:
                session.run(cypher)
            print("[GraphManager] Community Detection (Leiden) executed.")
        except Exception as e:
            print(f"[GraphManager] Community detection failed (GDS plugin may not be installed): {e}")

    def temporal_traversal(self, query_date: str, entity_name: str) -> List[Dict[str, Any]]:
        """
        Time-aware traversal: Returns treaties valid at query_date for entity.
        """
        if not self._connected:
            print("[GraphManager] Returning empty results (no connection)")
            return []
        
        cypher = """
        MATCH (e:Entity {name: $entity_name})-[:SIGNATORY_TO]->(t:Treaty)
        WHERE t.signed_date <= date($query_date)
        AND (t.end_date IS NULL OR t.end_date >= date($query_date))
        RETURN t.title as treaty, t.signed_date as signed, t.id as id
        ORDER BY t.signed_date DESC
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, entity_name=entity_name, query_date=query_date)
                return [record.data() for record in result]
        except Exception as e:
            print(f"[GraphManager] Temporal traversal failed: {e}")
            return []
    
    def multi_hop_query(self, start_entity: str, relationship_types: List[str], max_hops: int = 3) -> List[Dict[str, Any]]:
        """
        Multi-hop traversal: Follows relationship chain from start_entity.
        Example: Nation A -> Treaty B -> Resource C -> Nation D
        """
        if not self._connected:
            return []
        
        rel_pattern = "|".join(relationship_types) if relationship_types else "RELATED_TO"
        
        cypher = f"""
        MATCH path = (start:Entity {{name: $start_entity}})-[:{rel_pattern}*1..{max_hops}]-(end)
        RETURN [node in nodes(path) | node.name] as chain,
               [rel in relationships(path) | type(rel)] as relationships,
               length(path) as hops
        ORDER BY hops
        LIMIT 20
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, start_entity=start_entity)
                return [record.data() for record in result]
        except Exception as e:
            print(f"[GraphManager] Multi-hop query failed: {e}")
            return []
    
    def add_entity(self, name: str, entity_type: str, properties: Dict[str, Any] = None) -> bool:
        """Adds an entity to the graph."""
        if not self._connected:
            return False
        
        props = properties or {}
        props["name"] = name
        props["type"] = entity_type
        
        cypher = f"""
        MERGE (e:Entity {{name: $name}})
        SET e += $props
        RETURN e
        """
        try:
            with self.driver.session() as session:
                session.run(cypher, name=name, props=props)
            return True
        except Exception as e:
            print(f"[GraphManager] Add entity failed: {e}")
            return False
    
    def add_relationship(self, from_entity: str, to_entity: str, rel_type: str, properties: Dict[str, Any] = None) -> bool:
        """Adds a relationship between entities."""
        if not self._connected:
            return False
        
        props = properties or {}
        
        cypher = f"""
        MATCH (a:Entity {{name: $from_entity}})
        MATCH (b:Entity {{name: $to_entity}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN r
        """
        try:
            with self.driver.session() as session:
                session.run(cypher, from_entity=from_entity, to_entity=to_entity, props=props)
            return True
        except Exception as e:
            print(f"[GraphManager] Add relationship failed: {e}")
            return False
    
    # ============ Leiden Clustering & Community Summaries ============
    
    def get_community_summary(self, community_id: int) -> Dict[str, Any]:
        """
        Get summary of a geopolitical community detected by Leiden.
        
        Returns:
            {
                "community_id": 1,
                "members": ["India", "Japan", "Australia", "USA"],
                "relationship_types": ["ALLY", "TRADE_PARTNER", "QUAD_MEMBER"],
                "summary": "Indo-Pacific Strategic Partners"
            }
        """
        if not self._connected:
            return {"community_id": community_id, "members": [], "error": "No connection"}
        
        cypher = """
        MATCH (e:Entity)
        WHERE e.communityId = $community_id
        OPTIONAL MATCH (e)-[r]-(other:Entity {communityId: $community_id})
        RETURN collect(DISTINCT e.name) as members,
               collect(DISTINCT type(r)) as relationship_types
        LIMIT 1
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, community_id=community_id)
                record = result.single()
                
                if record:
                    members = record["members"][:20]  # Limit
                    rel_types = record["relationship_types"][:10]
                    
                    # Generate summary based on members
                    summary = self._generate_community_summary(members, rel_types)
                    
                    return {
                        "community_id": community_id,
                        "members": members,
                        "relationship_types": rel_types,
                        "summary": summary
                    }
                    
        except Exception as e:
            print(f"[GraphManager] Community summary failed: {e}")
        
        return {"community_id": community_id, "members": [], "error": "Query failed"}
    
    def _generate_community_summary(self, members: List[str], rel_types: List[str]) -> str:
        """Generate a human-readable summary for a community."""
        # Detect community type based on members
        member_set = {m.lower() for m in members}
        
        if {"india", "japan", "australia"} & member_set:
            if "usa" in member_set or "united states" in member_set:
                return "Indo-Pacific QUAD Partners"
        
        if {"china", "russia"} & member_set:
            return "Eurasian Strategic Partners"
        
        if {"india", "bangladesh", "nepal", "bhutan", "sri lanka"} & member_set:
            return "South Asian Regional Partners"
        
        if "TRADE_PARTNER" in rel_types:
            return f"Trade Partnership Network ({len(members)} members)"
        
        if "SIGNATORY_TO" in rel_types:
            return f"Treaty Signatories ({len(members)} members)"
        
        return f"Geopolitical Community ({len(members)} members)"
    
    def get_all_communities(self) -> List[Dict[str, Any]]:
        """Get all detected communities with summaries."""
        if not self._connected:
            return []
        
        cypher = """
        MATCH (e:Entity)
        WHERE e.communityId IS NOT NULL
        RETURN DISTINCT e.communityId as community_id, 
               count(e) as member_count
        ORDER BY member_count DESC
        LIMIT 20
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher)
                communities = []
                
                for record in result:
                    community = self.get_community_summary(record["community_id"])
                    community["member_count"] = record["member_count"]
                    communities.append(community)
                
                return communities
                
        except Exception as e:
            print(f"[GraphManager] Get all communities failed: {e}")
            return []
    
    def find_entity_community(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Find which community an entity belongs to."""
        if not self._connected:
            return None
        
        cypher = """
        MATCH (e:Entity {name: $entity_name})
        RETURN e.communityId as community_id
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, entity_name=entity_name)
                record = result.single()
                
                if record and record["community_id"] is not None:
                    return self.get_community_summary(record["community_id"])
                    
        except Exception as e:
            print(f"[GraphManager] Find entity community failed: {e}")
        
        return None
    
    def get_cross_community_relationships(
        self, 
        community_a: int, 
        community_b: int
    ) -> List[Dict[str, Any]]:
        """Get relationships between two communities (useful for conflict analysis)."""
        if not self._connected:
            return []
        
        cypher = """
        MATCH (a:Entity {communityId: $community_a})-[r]-(b:Entity {communityId: $community_b})
        RETURN a.name as entity_a, type(r) as relationship, b.name as entity_b
        LIMIT 50
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, community_a=community_a, community_b=community_b)
                return [record.data() for record in result]
                
        except Exception as e:
            print(f"[GraphManager] Cross-community query failed: {e}")
            return []

