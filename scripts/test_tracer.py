import os, sys, asyncio, glob, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FORCE_MINISTER_HEURISTIC"] = "1"

async def main():
    from dip.ind_diplomat import diplomat_query
    r = await diplomat_query("Test step tracer system", "IND")
    d = r.dict() if hasattr(r, "dict") else r
    tid = d.get("trace_id", "?")
    print(f"Trace ID: {tid}")
    print(f"Status: {d.get('status')} | Threat: {d.get('threat_level')}")
    
    # List trace files
    import glob
    files = sorted(glob.glob(f"data/traces/{tid}/*.json"))
    print(f"\nTrace files: {len(files)}")
    for f in files:
        with open(f) as fh:
            step = json.load(fh)
        print(f"  {step.get('step','?'):25s} | source: {step.get('source_file','?')}")
    
    # Show index
    idx = f"data/traces/{tid}/steps_index.txt"
    if os.path.exists(idx):
        print(f"\nStep index:")
        with open(idx) as fh:
            print(fh.read())

asyncio.run(main())
