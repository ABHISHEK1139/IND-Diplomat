import os
import json
import sqlite3
import datetime
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Manages the Obsidian-compatible Memory Vault.
    Stores intelligence as Markdown files with YAML frontmatter.
    Maintains a SQLite index for fast querying.
    """
    def __init__(self, vault_path: str = "engine/MemoryVault"):
        self.vault_path = vault_path
        self.db_path = os.path.join(vault_path, "index.db")
        self._initialize_vault()
        
    def _initialize_vault(self):
        os.makedirs(self.vault_path, exist_ok=True)
        # Initialize SQLite index
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    tags TEXT,
                    timestamp TEXT,
                    file_path TEXT
                )
            ''')
            conn.commit()

    def store_intelligence(self, doc_id: str, title: str, content: str, metadata: Dict[str, Any]):
        """
        Writes a Markdown file with YAML frontmatter.
        """
        timestamp = datetime.datetime.now().isoformat()
        tags = metadata.get('tags', [])
        tags_str = ", ".join(tags)
        
        # Build YAML frontmatter
        yaml_lines = [
            "---",
            f"id: {doc_id}",
            f"title: \"{title}\"",
            f"timestamp: {timestamp}",
            f"tags: [{tags_str}]",
        ]
        for k, v in metadata.items():
            if k not in ['tags', 'id', 'title', 'timestamp']:
                yaml_lines.append(f"{k}: {v}")
        yaml_lines.append("---\n")
        
        file_content = "\n".join(yaml_lines) + "\n" + content
        
        # Ensure title is safe for filename
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        filename = f"{timestamp[:10]}_{safe_title.replace(' ', '_')}.md"
        file_path = os.path.join(self.vault_path, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
            
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO documents (id, title, tags, timestamp, file_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (doc_id, title, json.dumps(tags), timestamp, file_path))
            conn.commit()
            
        logger.info("[MemoryManager] Stored intelligence: %s", filename)
        return file_path

    def query_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Queries the SQLite index for recent intelligence.
        """
        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, title, tags, timestamp, file_path 
                FROM documents 
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "tags": json.loads(row[2]),
                    "timestamp": row[3],
                    "file_path": row[4]
                })
        return results

    def read_document(self, file_path: str) -> str:
        """
        Reads a document's full content (including frontmatter).
        """
        if not os.path.exists(file_path):
            return ""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
