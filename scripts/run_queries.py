"""Run DIP 2.0 with real queries and save outputs."""
import asyncio, json, os, sys, time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FORCE_MINISTER_HEURISTIC", "1")  # Fast mode: no LLM calls

async def run_query(query, country):
    from dip.ind_diplomat import diplomat_query
    return await diplomat_query(query, country)

async def main():
    queries = [
        ("Assess India-China border tensions in Ladakh after recent troop movements", "IND"),
        ("Evaluate Pakistan economic coercion and hybrid warfare risk", "PAK"),
        ("Analyze Taiwan Strait military balance and escalation risk", "TWN"),
        ("Assess Russia-Ukraine conflict trajectory and NATO response", "RUS"),
        ("Evaluate Middle East stability after Israel-Iran tensions", "ISR"),
    ]
    
    os.makedirs("data/outputs", exist_ok=True)
    summary = []
    
    for q, c in queries:
        print(f"\n{'='*60}")
        print(f"QUERY: {q[:60]}... | COUNTRY: {c}")
        print(f"{'='*60}")
        t0 = time.time()
        try:
            r = await run_query(q, c)
            elapsed = time.time() - t0
            
            # Handle DiplomatResult, SimpleNamespace, dict, etc.
            if hasattr(r, 'dict'):
                r = r.dict()
            elif hasattr(r, 'model_dump'):
                r = r.model_dump(mode='json')
            elif hasattr(r, '__dict__') and not isinstance(r, dict):
                r = r.__dict__
            
            if isinstance(r, dict):
                status = r.get("status", "?")
                threat = r.get("threat_level", "?")
                sre = (r.get("nextgen_sre") or {}).get("sre_escalation_score", "?")
                ver = r.get("verification_score", "?")
                hyps = len(r.get("hypotheses", []))
                obs = r.get("observation_count", 0)
                
                print(f"Status: {status} | Threat: {threat} | SRE: {sre}")
                print(f"Verification: {ver} | Hypotheses: {hyps} | Observations: {obs} | Time: {elapsed:.1f}s")
                
                # Save
                fn = f"data/outputs/output_{c}_{q[:30].replace(' ', '_').replace('-','')}.json"
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(r, f, indent=2, default=str, ensure_ascii=False)
                print(f"Saved: {fn}")
                
                summary.append({
                    "query": q[:60],
                    "country": c,
                    "status": status,
                    "threat_level": threat,
                    "sre_score": sre,
                    "verification": ver,
                    "hypotheses": hyps,
                    "observations": obs,
                    "elapsed": round(elapsed, 1),
                })
            else:
                print(f"ERROR: Unexpected result type: {type(r)}")
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    # Save summary
    with open("data/outputs/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print("ALL QUERIES COMPLETE")
    print(f"Total: {len(summary)} queries, {sum(s['elapsed'] for s in summary):.1f}s")
    for s in summary:
        print(f"  {s['country']}: {s['status']:12s} | Threat: {s['threat_level']:10s} | SRE: {s['sre_score']} | {s['elapsed']}s")

if __name__ == "__main__":
    asyncio.run(main())
