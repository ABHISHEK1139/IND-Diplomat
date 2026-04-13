"""
Knowledge Acquisition Console (Admin Panel)

Run:
    cd IND-Dip
    streamlit run Scripts/console_ui.py
"""

import os
import json
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from console_store import (
    list_countries,
    upsert_country,
    list_legal_docs,
    add_legal_doc,
    list_sources,
    upsert_source,
    list_logs,
    get_api_keys,
    save_api_keys,
    now_iso,
    new_doc_id,
    DATA_DIR,
    COUNTRIES_PATH,
    LEGAL_DOCS_PATH,
    SOURCES_PATH,
    API_KEYS_PATH,
)

SOURCES_YAML = ROOT / "feeder" / "sources.yaml"
RECORDS_DIR = ROOT / "data" / "archive" / "records"


# --------------------------------------------------------------------------- utils

def count_sources():
    if not SOURCES_YAML.exists():
        return 0
    import yaml
    with SOURCES_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return len(data.get("sources", []))


def latest_ingest_ts():
    if not RECORDS_DIR.exists():
        return "—"
    files = sorted(RECORDS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    if not files:
        return "—"
    with files[0].open("r", encoding="utf-8") as f:
        rec = json.load(f)
    return rec.get("collected_at", "—")


def today_new_docs():
    if not RECORDS_DIR.exists():
        return 0
    today = date.today().isoformat()
    count = 0
    for p in RECORDS_DIR.glob("*.json"):
        try:
            with p.open("r", encoding="utf-8") as f:
                rec = json.load(f)
            if rec.get("collected_at", "").startswith(today):
                count += 1
        except Exception:
            continue
    return count


# --------------------------------------------------------------------------- UI

st.set_page_config(page_title="Knowledge Acquisition Console", layout="wide")

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Pages",
    ["Dashboard", "Countries", "Legal Foundations", "Data Sources", "Ingestion Monitor", "Settings"],
    index=0,
)

st.sidebar.caption(f"Config dir: {DATA_DIR}")

# Dashboard --------------------------------------------------------------------
if page == "Dashboard":
    st.title("Dashboard")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Countries", len(list_countries()))
    c2.metric("Legal Docs", len(list_legal_docs()))
    c3.metric("Sources", count_sources())
    c4.metric("Last Ingest", latest_ingest_ts())
    c5.metric("New Docs Today", today_new_docs())

    st.write("Use the sidebar to add countries and legal documents. Data Sources and Monitor will come next.")

# Countries --------------------------------------------------------------------
elif page == "Countries":
    st.title("Countries Registry")
    countries = list_countries()
    if countries:
        st.subheader("Existing Countries")
        st.dataframe(countries, use_container_width=True)
    else:
        st.info("No countries yet. Add one below.")

    st.subheader("Add / Update Country")
    with st.form("add_country"):
        name = st.text_input("Country Name")
        code = st.text_input("Short Code (IND, USA, CHN)").upper()
        region = st.text_input("Region", value="")
        gov_type = st.text_input("Government Type", value="")
        capital = st.text_input("Capital", value="")
        notes = st.text_area("Notes", value="")
        extra_meta = st.text_area("Extra metadata (JSON)", value="{}", help="Optional free-form fields for future use")
        submitted = st.form_submit_button("Save Country")

    if submitted:
        if not name or not code:
            st.error("Name and Short Code are required.")
        else:
            try:
                extra = json.loads(extra_meta or "{}")
            except Exception:
                st.error("Extra metadata must be valid JSON.")
                extra = {}
            record = {
                "id": code,
                "name": name,
                "region": region,
                "government_type": gov_type,
                "capital": capital,
                "notes": notes,
                "created_at": now_iso(),
                "metadata": extra,
            }
            upsert_country(record)
            st.success(f"Saved country {code}")

# Legal Foundations -----------------------------------------------------------
elif page == "Legal Foundations":
    st.title("Legal Foundations")
    docs = list_legal_docs()
    if docs:
        st.subheader("Registered Legal Documents")
        st.dataframe(
            [
                {
                    "title": d.get("title"),
                    "country": d.get("country"),
                    "type": d.get("type"),
                    "effective_date": d.get("effective_date"),
                    "has_file": bool(d.get("file_path")),
                }
                for d in docs
            ],
            use_container_width=True,
        )
    else:
        st.info("No legal documents yet.")

    st.subheader("Add Legal Document")
    countries = list_countries()
    country_codes = [c["id"] for c in countries] if countries else []
    with st.form("add_legal_doc"):
        title = st.text_input("Title")
        country = st.selectbox("Country", country_codes) if country_codes else st.text_input("Country Code")
        organization = st.text_input("Organization (UN, WTO, Parliament, etc.)", value="")
        doc_type = st.selectbox("Document Type", ["constitution", "treaty", "law", "agreement", "regulation"])
        effective_date = st.date_input("Effective Date", value=None)
        amendment_date = st.date_input("Last Amendment Date", value=None)
        source_url = st.text_input("Official URL (optional)", value="")
        has_chapters = st.checkbox("Contains Chapters/Parts", value=True)
        has_articles = st.checkbox("Contains Articles/Clauses", value=True)
        upload = st.file_uploader("Upload PDF", type=["pdf"])
        extra_meta = st.text_area("Extra metadata (JSON)", value="{}", help="Optional: e.g., jurisdiction tags")
        submitted = st.form_submit_button("Save Legal Document")

    if submitted:
        if not title or not country:
            st.error("Title and Country are required.")
        else:
            try:
                extra = json.loads(extra_meta or "{}")
            except Exception:
                st.error("Extra metadata must be valid JSON.")
                extra = {}
            doc_id = new_doc_id()
            file_path = ""
            if upload:
                upload_dir = ROOT / "data" / "legal" / "uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / f"{doc_id}.pdf"
                with open(file_path, "wb") as f:
                    f.write(upload.read())
                file_path = str(file_path.relative_to(ROOT))

            record = {
                "id": doc_id,
                "title": title,
                "country": country,
                "organization": organization or None,
                "type": doc_type,
                "effective_date": effective_date.isoformat() if isinstance(effective_date, date) else None,
                "last_amendment_date": amendment_date.isoformat() if isinstance(amendment_date, date) else None,
                "source_url": source_url or None,
                "file_path": file_path,
                "has_chapters": has_chapters,
                "has_articles": has_articles,
                "status": "pending_parse",
                "created_at": now_iso(),
                "metadata": extra,
            }
            add_legal_doc(record)
            st.success(f"Saved legal document {title}")

# Stubs -----------------------------------------------------------------------
elif page == "Data Sources":
    st.title("Data Sources (Events / Foundations)")
    st.markdown("The system supports five source components:")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.info("1) API\nExample: WTO notifications\nCollector: requests/json")
    c2.info("2) RSS Feed\nExample: UN News\nCollector: feedparser")
    c3.info("3) HTML Website\nExample: Government press pages\nCollector: crawler + parser")
    c4.info("4) Document Repository (PDF)\nExample: Treaty archives\nCollector: link crawler")
    c5.info("5) Bulk Dataset\nExample: Data portals\nCollector: downloader")
    sources = list_sources()
    if sources:
        st.subheader("Configured Sources")
        st.dataframe(
            [
                {
                    "name": s.get("name"),
                    "type": s.get("source_type"),
                    "country": s.get("country"),
                    "org": s.get("organization"),
                    "priority": s.get("priority"),
                    "interval": s.get("schedule"),
                    "category": s.get("category"),
                }
                for s in sources
            ],
            use_container_width=True,
        )
    else:
        st.info("No sources yet.")

    st.subheader("Add / Update Source")
    with st.form("add_source"):
        name = st.text_input("Source Name")
        country = st.text_input("Country Code", value="")
        organization = st.text_input("Organization", value="")
        category = st.selectbox(
            "Category",
            ["diplomatic_statement", "trade_notification", "policy_announcement", "sanction_notice", "other"],
        )
        data_role = st.selectbox("Data Role", ["event", "foundational"], index=0, help="event = dynamic; foundational = slow-changing law/rules")
        domain_tags = st.text_input("Domain Tags (comma-separated)", value="country_profile,law")
        source_type = st.selectbox("Source Type", ["API", "RSS", "HTML", "PDF Repository", "Bulk Dataset"])
        priority = st.slider("Priority (1=highest)", 1, 5, 2)
        schedule = st.text_input("Crawl Interval (cron)", value="0 */6 * * *")
        base_url = st.text_input("Base URL / Feed / Listing URL")

        st.markdown("**Type-specific settings**")
        api_params = st.text_area("API Params (JSON key/values)", value="{}", help="Only used for API type")
        api_auth = st.text_input("API Auth Key/Header", value="", help="Only for API")
        rss_filter = st.text_input("RSS keyword filter (optional)", value="", help="Only for RSS")
        html_link_selector = st.text_input("Article link selector (CSS)", value="", help="HTML/PDF repo")
        html_title_selector = st.text_input("Title selector (CSS)", value="", help="HTML")
        html_date_selector = st.text_input("Date selector (CSS)", value="", help="HTML")
        html_content_selector = st.text_input("Content selector (CSS)", value="", help="HTML")
        file_ext = st.text_input("File extension filter (.pdf)", value=".pdf", help="PDF Repository")
        bulk_format = st.selectbox("Bulk format", ["csv", "json", "zip", "other"], index=0, help="Bulk Dataset")
        tags = st.text_input("Tags (comma-separated)", value="")
        schema_hint = st.text_area("What does this source return? (schema/fields)", value="e.g., country, region, neighbors, laws, constitution, temporal events")
        extra_meta = st.text_area("Extra metadata (JSON)", value="{}", help="Optional: add arbitrary fields for future use")

        submitted = st.form_submit_button("Save Source")

    if submitted:
        if not name or not base_url:
            st.error("Name and Base URL are required.")
        else:
            try:
                import json as js
                params_parsed = js.loads(api_params or "{}")
            except Exception:
                st.error("API Params must be valid JSON.")
                params_parsed = {}
            try:
                extra = json.loads(extra_meta or "{}")
            except Exception:
                st.error("Extra metadata must be valid JSON.")
                extra = {}

            record = {
                "name": name,
                "country": country or None,
                "organization": organization or None,
                "category": category,
                "data_role": data_role,
                "domain_tags": [t.strip() for t in domain_tags.split(",") if t.strip()],
                "source_type": source_type,
                "priority": int(priority),
                "schedule": schedule,
                "base_url": base_url,
                "api_params": params_parsed if source_type == "API" else None,
                "api_auth": api_auth if source_type == "API" else None,
                "rss_filter": rss_filter if source_type == "RSS" else None,
                "html": {
                    "link_selector": html_link_selector,
                    "title_selector": html_title_selector,
                    "date_selector": html_date_selector,
                    "content_selector": html_content_selector,
                } if source_type in ["HTML", "PDF Repository"] else None,
                "file_ext": file_ext if source_type == "PDF Repository" else None,
                "bulk_format": bulk_format if source_type == "Bulk Dataset" else None,
                "schema_hint": schema_hint or None,
                "status": "active",
                "created_at": now_iso(),
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
                "metadata": extra,
            }
            upsert_source(record)
            st.success(f"Saved source {name}")

elif page == "Ingestion Monitor":
    st.title("Ingestion Monitor")
    logs = list_logs()
    if logs:
        st.dataframe(logs, use_container_width=True)
    else:
        st.info("No logs yet. Run the feeder to populate.")

    st.markdown("### Latest Records (from archive)")
    if RECORDS_DIR.exists():
        recs = sorted(RECORDS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)[:20]
        rows = []
        for p in recs:
            try:
                with p.open("r", encoding="utf-8") as f:
                    r = json.load(f)
                rows.append(
                    {
                        "title": r.get("title"),
                        "source": r.get("source"),
                        "type": r.get("document_type"),
                        "collected_at": r.get("collected_at"),
                        "path": str(p.relative_to(ROOT)),
                    }
                )
            except Exception:
                continue
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No record files found.")
    else:
        st.info("Archive directory not found.")

# Settings ---------------------------------------------------------------------
elif page == "Settings":
    st.title("Settings")
    st.markdown("Manage API keys and config paths.")

    st.subheader("API Keys")
    existing_keys = get_api_keys()
    default_keys = {
        "WTO_API_KEY": "",
        "UNCTAD_CLIENT_ID": "",
        "UNCTAD_CLIENT_SECRET": "",
        "COMTRADE_API_KEY": "",
        "GENERIC_API_KEY": "",
    }
    for k, v in default_keys.items():
        existing_keys.setdefault(k, v)

    with st.form("api_keys"):
        new_keys = {}
        st.markdown("Existing keys (password fields, blanks are allowed):")
        for key_name in existing_keys:
            new_keys[key_name] = st.text_input(key_name, value=existing_keys.get(key_name, ""), type="password")
        st.markdown("Add a custom key (optional):")
        custom_key = st.text_input("Custom Key Name", value="")
        custom_val = st.text_input("Custom Key Value", value="", type="password")
        submitted = st.form_submit_button("Save API Keys")
    if submitted:
        if custom_key:
            new_keys[custom_key] = custom_val
        save_api_keys(new_keys)
        st.success("API keys saved locally.")

    st.subheader("Paths (read-only)")
    st.code(f"Countries: {COUNTRIES_PATH}")
    st.code(f"Legal docs: {LEGAL_DOCS_PATH}")
    st.code(f"Sources: {SOURCES_PATH}")
    st.code(f"API keys: {API_KEYS_PATH}")
