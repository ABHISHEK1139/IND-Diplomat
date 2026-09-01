import os
import json
import csv
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger("DIP.NextGen.MultiformatExporter")

def export_all(result: Dict[str, Any], session: Any, output_dir: str = "exports") -> Dict[str, str]:
    """
    Exports the pipeline result into multiple formats:
    - JSON (Raw Data)
    - Markdown (Strategic Narrative)
    - CSV (Research Log & Evidentiary Base)
    - GraphML (Mocked for Neo4j)
    - STIX 2.1 (Using stix2_exporter)
    """
    os.makedirs(output_dir, exist_ok=True)
    job_id = result.get("trace_id", "unknown_job")
    paths = {}
    
    # 1. JSON Export
    json_path = os.path.join(output_dir, f"{job_id}_raw.json")
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        paths["json"] = json_path
    except Exception as e:
        logger.error(f"Failed to export JSON: {e}")

    # 2. Markdown Export (Strategic Narrative)
    md_path = os.path.join(output_dir, f"{job_id}_narrative.md")
    try:
        narrative_md = result.get("strategic_narrative_md", "")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(narrative_md)
        paths["markdown"] = md_path
    except Exception as e:
        logger.error(f"Failed to export Markdown: {e}")

    # 3. CSV Export (Research Log)
    csv_path = os.path.join(output_dir, f"{job_id}_research_log.csv")
    try:
        research_log = result.get("research_log", [])
        if research_log:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["query", "priority", "status", "evidence_found", "cost_usd", "time_ms"])
                writer.writeheader()
                for entry in research_log:
                    rfi = entry.get("rfi", {})
                    writer.writerow({
                        "query": rfi.get("query", ""),
                        "priority": rfi.get("priority", ""),
                        "status": entry.get("status", ""),
                        "evidence_found": entry.get("evidence_found", 0),
                        "cost_usd": rfi.get("estimated_cost_usd", 0.0),
                        "time_ms": entry.get("execution_time_ms", 0.0)
                    })
        paths["csv"] = csv_path
    except Exception as e:
        logger.error(f"Failed to export CSV: {e}")

    # 4. GraphML Export (Mock representation of Knowledge Graph)
    graphml_path = os.path.join(output_dir, f"{job_id}_graph.graphml")
    try:
        # Simplified GraphML representation for the nodes
        gml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        gml += '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        gml += '  <graph id="G" edgedefault="directed">\n'
        
        # Add a node for the country/target
        target = result.get("country", "Target")
        gml += f'    <node id="{target}"/>\n'
        
        # Add nodes for each RFI
        for i, entry in enumerate(result.get("research_log", [])):
            gml += f'    <node id="RFI_{i}"/>\n'
            gml += f'    <edge source="RFI_{i}" target="{target}"/>\n'
            
        gml += '  </graph>\n</graphml>'
        
        with open(graphml_path, 'w', encoding='utf-8') as f:
            f.write(gml)
        paths["graphml"] = graphml_path
    except Exception as e:
        logger.error(f"Failed to export GraphML: {e}")

    # 5. STIX Export
    try:
        from dip.engines.stix2_exporter import export_stix_bundle
        stix_bundle = export_stix_bundle(result, session)
        if stix_bundle:
            stix_path = os.path.join(output_dir, f"{job_id}_stix.json")
            with open(stix_path, 'w', encoding='utf-8') as f:
                json.dump(stix_bundle, f, indent=2)
            paths["stix2"] = stix_path
    except Exception as e:
        logger.debug(f"STIX2 export skipped or failed: {e}")

    return paths
