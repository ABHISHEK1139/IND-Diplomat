"""Controlled repair actions for Layer-0 System Guardian."""

from __future__ import annotations

import subprocess
import sys
from typing import Dict

# Strict allowlist: the guardian can only install known packages.
PACKAGE_INSTALL_MAP: Dict[str, str] = {
    "pytesseract": "pytesseract==0.3.13",
    "bs4": "beautifulsoup4==4.14.3",
    "ddgs": "ddgs==9.10.0",
    "sentence_transformers": "sentence-transformers==5.2.3",
    "chromadb": "chromadb==1.5.1",
    "spacy": "spacy==3.8.11",
    "pandas": "pandas==3.0.1",
    "faiss": "faiss-cpu==1.13.2",
}


def _run_pip(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pip", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
        check=False,
    )


def install_python_package(import_name: str) -> str:
    spec = PACKAGE_INSTALL_MAP.get(import_name)
    if not spec:
        return f"Skipped non-allowlisted package: {import_name}"
    result = _run_pip(["install", spec])
    if result.returncode == 0:
        return f"Installed/verified python package: {spec}"
    error = (result.stderr or result.stdout or "").strip().splitlines()[-1:]
    tail = error[0] if error else "unknown error"
    return f"Failed to install {spec}: {tail}"


def fix_ddgs() -> str:
    uninstall_result = _run_pip(["uninstall", "duckduckgo_search", "-y"])
    install_result = _run_pip(["install", "-U", "ddgs==9.10.0"])
    if install_result.returncode == 0:
        if uninstall_result.returncode == 0:
            return "Repaired internet search module: removed duckduckgo_search and installed ddgs==9.10.0"
        return "Installed internet search module: ddgs==9.10.0"
    error = (install_result.stderr or install_result.stdout or "").strip().splitlines()[-1:]
    tail = error[0] if error else "unknown error"
    return f"Failed to repair ddgs: {tail}"


def instructions_for_tesseract() -> str:
    return (
        "Tesseract OCR is missing.\n\n"
        "Please install manually:\n"
        "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
        "Then restart system."
    )

def clear_redis_cache() -> str:
    """Clear the entire redis cache to fix stale data or memory issues."""
    try:
        import redis
        r = redis.Redis.from_url("redis://redis:6379/0")
        r.flushall()
        return "Successfully cleared all Redis caches."
    except Exception as e:
        return f"Failed to clear Redis: {str(e)}"

def flush_neo4j() -> str:
    """Wipe the neo4j database to reset world state."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "password"))
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        return "Successfully flushed Neo4j graph database."
    except Exception as e:
        return f"Failed to flush Neo4j: {str(e)}"
