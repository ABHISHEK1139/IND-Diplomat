"""
Memory Vault (Layer 6)
======================
Stores intelligence reports as Markdown files with YAML frontmatter.
Now integrated with ChromaDB for semantic search retrieval.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None

logger = logging.getLogger("Memory.vault")

class MemoryVault:
    def __init__(self, vault_path: str = None):
        if vault_path is None:
            self.vault_path = os.path.join(os.path.dirname(__file__), "..", "data", "memory_vault")
        else:
            self.vault_path = vault_path
            
        self.db_path = os.path.join(self.vault_path, "index.db")
        self._initialize_vault()
        
        # Initialize ChromaDB Vector Store
        self.chroma_client = None
        self.collection = None
        if chromadb:
            try:
                chroma_path = os.path.join(self.vault_path, "chroma_db")
                self.chroma_client = chromadb.PersistentClient(path=chroma_path)
                self.collection = self.chroma_client.get_or_create_collection(name="intelligence_reports")
                logger.info("ChromaDB initialized for semantic memory.")
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")

    def _initialize_vault(self):
        os.makedirs(self.vault_path, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    tags TEXT,
                    timestamp TEXT,
                    threat_level TEXT,
                    confidence REAL,
                    file_path TEXT
                )
            ''')
            conn.commit()

    def store_intelligence(self, doc_id: str, title: str, content: str, metadata: Dict[str, Any]) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        tags = metadata.get('tags', [])
        threat_level = metadata.get('threat_level', 'UNKNOWN')
        confidence = float(metadata.get('confidence', 0.0))
        
        tags_str = ", ".join(tags)
        
        # YAML Frontmatter
        yaml_lines = [
            "---",
            f"id: {doc_id}",
            f"title: \"{title}\"",
            f"timestamp: {timestamp}",
            f"threat_level: {threat_level}",
            f"confidence: {confidence}",
            f"tags: [{tags_str}]",
        ]
        for k, v in metadata.items():
            if k not in ['tags', 'id', 'title', 'timestamp', 'threat_level', 'confidence']:
                yaml_lines.append(f"{k}: {v}")
        yaml_lines.append("---\n")
        
        file_content = "\n".join(yaml_lines) + "\n" + content
        
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip().replace(' ', '_')
        filename = f"{timestamp[:10]}_{safe_title}.md"
        file_path = os.path.join(self.vault_path, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
            
        # 1. Save to SQLite Metadata Index
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO documents 
                (id, title, tags, timestamp, threat_level, confidence, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, title, json.dumps(tags), timestamp, threat_level, confidence, file_path))
            conn.commit()
            
        # 2. Save to ChromaDB for Semantic Search
        if self.collection:
            try:
                self.collection.add(
                    documents=[content],
                    metadatas=[{"title": title, "threat_level": threat_level, "timestamp": timestamp}],
                    ids=[doc_id]
                )
            except Exception as e:
                logger.error(f"Failed to add to ChromaDB: {e}")
            
        logger.info(f"Stored intelligence: {filename}")
        return file_path

    def semantic_search(self, query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Search past intelligence reports by semantic meaning rather than exact tags."""
        if not self.collection:
            logger.warning("ChromaDB not available, falling back to recent query.")
            return self.query_recent(n_results)
            
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            structured_results = []
            if results and results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    doc_id = results['ids'][0][i]
                    meta = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if 'distances' in results and results['distances'] else 0.0
                    
                    structured_results.append({
                        "id": doc_id,
                        "title": meta.get("title", "Unknown"),
                        "threat_level": meta.get("threat_level", "UNKNOWN"),
                        "distance": distance,
                        "content_snippet": results['documents'][0][i][:200] + "..." if results['documents'] else ""
                    })
            return structured_results
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def query_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, title, tags, timestamp, threat_level, confidence, file_path 
                FROM documents 
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "tags": json.loads(row[2]),
                    "timestamp": row[3],
                    "threat_level": row[4],
                    "confidence": row[5],
                    "file_path": row[6]
                })
        return results

    def retrieve_similar_crises(self, current_state_context: str) -> List[Dict[str, Any]]:
        """Retrieve the 3 most similar past crises using keyword matching."""
        keywords = set(w.strip('.,!?()[]{}""\'') for w in current_state_context.lower().split())
        keywords = {w for w in keywords if len(w) > 2}
        
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT id, title, tags, timestamp, threat_level, confidence, file_path 
                    FROM documents 
                ''')
                
                scored_crises = []
                for row in cursor.fetchall():
                    doc_id, title, tags_json, timestamp, threat_level, confidence, file_path = row
                    tags = json.loads(tags_json) if tags_json else []
                    
                    score = 0
                    title_words = set(w.strip('.,!?()[]{}""\'') for w in title.lower().split())
                    score += len(keywords.intersection(title_words))
                    
                    tag_words = set(t.lower() for t in tags)
                    score += len(keywords.intersection(tag_words)) * 2
                    
                    scored_crises.append({
                        "score": score,
                        "crisis": {
                            "id": doc_id,
                            "title": title,
                            "tags": tags,
                            "timestamp": timestamp,
                            "threat_level": threat_level,
                            "confidence": confidence,
                            "file_path": file_path
                        }
                    })
                        
                scored_crises.sort(key=lambda x: (x["score"], x["crisis"]["timestamp"]), reverse=True)
                results = [item["crisis"] for item in scored_crises[:3]]
                
        except Exception as e:
            logger.error(f"Failed to retrieve similar crises: {e}")
            
        return results

    def read_document(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
