"""Phase 3: Layer 2 search verification."""
import sys, os, traceback
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("search_results.log"), "w", encoding="utf-8")

try:
    from engine.Layer2_Knowledge.knowledge_api import KnowledgeAPI, KnowledgeRequest
    ka = KnowledgeAPI()
    req = KnowledgeRequest(query="India Pakistan relations", top_k=5)
    resp = ka.search(req)
    out.write(f"OK: result_count={resp.metadata.get('result_count')}\n")
    out.write(f"  resolved_spaces={resp.metadata.get('resolved_spaces')}\n")
    out.write(f"  source={resp.source}\n")
    for i, doc in enumerate(resp.documents[:3]):
        title = doc.get('title', doc.get('content', '')[:60])
        score = doc.get('score', doc.get('distance', '?'))
        out.write(f"  [{i+1}] score={score} | {title}\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

out.close()
print("Done")
