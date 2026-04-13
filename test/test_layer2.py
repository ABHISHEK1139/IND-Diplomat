"""Phase 3: Layer 2 Knowledge Pipeline Verification."""
import sys, os, traceback
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("layer2_results.log"), "w", encoding="utf-8")

# 1. ChromaDB vector store
out.write("=== 1. Vector Store ===\n")
try:
    from engine.Layer2_Knowledge.vector_store import get_vector_store
    vs = get_vector_store()
    out.write(f"OK: vector_store type={type(vs).__name__}\n")
    # Try a basic operation
    if hasattr(vs, 'collection'):
        out.write(f"  collection={vs.collection.name}, count={vs.collection.count()}\n")
    elif hasattr(vs, '_collection'):
        out.write(f"  collection={vs._collection.name}, count={vs._collection.count()}\n")
    else:
        out.write(f"  attrs: {[a for a in dir(vs) if not a.startswith('__')][:10]}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

# 2. Retriever
out.write("\n=== 2. DiplomaticRetriever ===\n")
try:
    from engine.Layer2_Knowledge.retriever import DiplomaticRetriever
    dr = DiplomaticRetriever()
    out.write(f"OK: DiplomaticRetriever created, type={type(dr).__name__}\n")
    out.write(f"  methods: {[m for m in dir(dr) if not m.startswith('_')][:10]}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

# 3. KnowledgeAPI
out.write("\n=== 3. KnowledgeAPI ===\n")
try:
    from engine.Layer2_Knowledge.knowledge_api import KnowledgeAPI
    ka = KnowledgeAPI()
    out.write(f"OK: KnowledgeAPI created, type={type(ka).__name__}\n")
    out.write(f"  methods: {[m for m in dir(ka) if not m.startswith('_')][:10]}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

# 4. Multi-index
out.write("\n=== 4. MultiIndex ===\n")
try:
    from engine.Layer2_Knowledge.multi_index import multi_index_manager
    out.write(f"OK: multi_index_manager type={type(multi_index_manager).__name__}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

# 5. Entity registry
out.write("\n=== 5. EntityRegistry ===\n")
try:
    from engine.Layer2_Knowledge.entity_registry import entity_registry
    out.write(f"OK: entity_registry type={type(entity_registry).__name__}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

# 6. Source registry
out.write("\n=== 6. SourceRegistry ===\n")
try:
    from engine.Layer2_Knowledge.source_registry import source_registry
    out.write(f"OK: source_registry type={type(source_registry).__name__}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

# 7. Test a search query
out.write("\n=== 7. Search Test ===\n")
try:
    from engine.Layer2_Knowledge.knowledge_api import KnowledgeAPI
    ka = KnowledgeAPI()
    if hasattr(ka, 'search'):
        results = ka.search("India Pakistan relations", top_k=3)
        out.write(f"OK: search returned {len(results) if results else 0} results\n")
    elif hasattr(ka, 'query'):
        results = ka.query("India Pakistan relations", top_k=3)
        out.write(f"OK: query returned {len(results) if results else 0} results\n")
    else:
        out.write(f"INFO: KnowledgeAPI methods: {[m for m in dir(ka) if not m.startswith('_')]}\n")
except Exception:
    out.write(f"FAIL:\n")
    traceback.print_exc(file=out)

out.close()
print("Done")
