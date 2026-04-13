"""
Lightweight Streamlit UI for the feeder pipeline.

Features:
- View configured sources (from feeder/sources.yaml)
- Add a new source entry and save back to YAML
- Trigger a one-off crawl (priority filter optional)
- Inspect latest ingested records

Run:
    cd IND-Dip
    streamlit run Scripts/feeder_ui.py
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "feeder" / "sources.yaml"
RECORDS_DIR = ROOT / "data" / "archive" / "records"


def load_sources() -> Dict[str, Any]:
    if not SOURCES_PATH.exists():
        return {"sources": [], "config": {}}
    with SOURCES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"sources": [], "config": {}}


def save_sources(data: Dict[str, Any]) -> None:
    SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SOURCES_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def list_records(limit: int = 20) -> List[Dict[str, Any]]:
    if not RECORDS_DIR.exists():
        return []
    records = []
    for path in sorted(RECORDS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
        try:
            with path.open("r", encoding="utf-8") as f:
                rec = json.load(f)
                rec["__path"] = str(path.relative_to(ROOT))
                records.append(rec)
        except Exception:
            continue
    return records


def run_crawl(priority: int | None = None) -> List[Dict[str, Any]]:
    # Import lazily to avoid slowing UI startup
    import sys
    sys.path.insert(0, str(ROOT))
    from feeder.scheduler import ingestion_scheduler

    async def _run():
        return await ingestion_scheduler.run_all_sources(priority_filter=priority)

    return asyncio.run(_run())


def main():
    st.set_page_config(page_title="Feeder Control", layout="wide")
    st.title("Event Feeder Control Panel")

    tab_sources, tab_crawl, tab_records = st.tabs(["Sources", "Run Crawl", "Records"])

    with tab_sources:
        data = load_sources()
        st.subheader("Configured Sources")
        st.json(data.get("sources", []))

        st.markdown("### Add / Update Source")
        with st.form("add_source"):
            name = st.text_input("Name", help="Unique id, e.g., mea_india_press")
            url = st.text_input("URL")
            s_type = st.selectbox("Type", ["html", "rss", "pdf", "json"], index=0)
            category = st.text_input("Category", value="diplomatic_statement")
            knowledge_space = st.text_input("Knowledge Space", value="event")
            organization = st.text_input("Organization", value="")
            country = st.text_input("Country", value="India")
            priority = st.slider("Priority (1=high)", 1, 5, 2)
            schedule = st.text_input("Schedule (cron)", value="0 */6 * * *")
            description = st.text_area("Description", value="")
            submitted = st.form_submit_button("Save Source")

        if submitted:
            if not name or not url:
                st.error("Name and URL are required.")
            else:
                sources = data.get("sources", [])
                # upsert
                existing = next((s for s in sources if s.get("name") == name), None)
                new_entry = {
                    "name": name,
                    "type": s_type,
                    "url": url,
                    "category": category,
                    "knowledge_space": knowledge_space,
                    "organization": organization or None,
                    "priority": int(priority),
                    "schedule": schedule,
                    "country": country or None,
                    "description": description or "",
                }
                if existing:
                    sources = [new_entry if s.get("name") == name else s for s in sources]
                    st.success(f"Updated source {name}")
                else:
                    sources.append(new_entry)
                    st.success(f"Added source {name}")
                data["sources"] = sources
                save_sources(data)

    with tab_crawl:
        st.subheader("Run One-Off Crawl")
        priority_filter = st.selectbox("Priority filter", ["All", 1, 2, 3, 4, 5], index=1)
        if st.button("Run Crawl Now"):
            with st.spinner("Running crawl..."):
                results = run_crawl(None if priority_filter == "All" else int(priority_filter))
            st.success("Crawl complete")
            st.json([r.__dict__ if hasattr(r, "__dict__") else r for r in results])

    with tab_records:
        st.subheader("Latest Records")
        records = list_records(limit=30)
        if not records:
            st.info("No records yet.")
        for rec in records:
            with st.expander(f"{rec.get('title','(untitled)')} — {rec.get('source')}"):
                st.write(f"Collected: {rec.get('collected_at')}")
                st.write(f"URL: {rec.get('url')}")
                st.write(f"Publication date: {rec.get('publication_date')}")
                st.write(f"Type: {rec.get('document_type')} | Country: {rec.get('country')} | Org: {rec.get('organization')}")
                st.write(f"Raw file: `{rec.get('raw_file_path')}`")
                st.write(f"Text file: `{rec.get('text_file_path')}`")
                st.code(json.dumps(rec, indent=2), language="json")


if __name__ == "__main__":
    main()
