from typing import List, Dict


class PlaybookStore:
    """
    Minimal scenario playbook library.
    Each playbook has triggers (keywords), a short description,
    and suggested mitigations derived from industry war-gaming patterns.
    """

    def __init__(self):
        self.playbooks: List[Dict] = [
            {
                "id": "strait_of_hormuz_closure",
                "triggers": ["hormuz", "gulf shipping", "strait of hormuz"],
                "description": "Closure of the Strait of Hormuz disrupts 20% of global oil.",
                "branches": [
                    {"action": "divert", "detail": "Pre-book Suez and Cape routes; increase tanker availability."},
                    {"action": "stockpile", "detail": "Activate SPR drawdown protocols; secure refinery feedstock."},
                    {"action": "diplomacy", "detail": "Backchannel de-escalation via Oman/Qatar; request UN maritime corridor."},
                ],
            },
            {
                "id": "sudden_sanctions_shock",
                "triggers": ["sanction", "embargo", "export control"],
                "description": "Major economy imposes sudden sanctions on dual-use tech.",
                "branches": [
                    {"action": "reroute_supply", "detail": "Shift procurement to neutral hubs; pre-clear end-use certificates."},
                    {"action": "licence_fastlane", "detail": "Create rapid legal review cell for licences and carve-outs."},
                    {"action": "ally_coordination", "detail": "Coordinate with Quad/EU partners for synchronized waivers."},
                ],
            },
            {
                "id": "border_flare_up",
                "triggers": ["border", "incursion", "line of control", "laddakh", "ladakh"],
                "description": "Limited border flare-up risks escalation.",
                "branches": [
                    {"action": "rules_of_engagement", "detail": "Enforce de-escalatory ROE; avoid airspace incursions."},
                    {"action": "hotline", "detail": "Activate DGMO/foreign office hotlines for immediate clarification."},
                    {"action": "media_ops", "detail": "Single narrative cell to avoid misinformation spiral."},
                ],
            },
            {
                "id": "risk_assessment",
                "triggers": ["threat", "risk", "danger", "security", "stability", "war", "escalation"],
                "description": "Comprehensive single-actor threat and stability assessment.",
                "branches": [
                    {"action": "monitor_indicators", "detail": "Track mobilization, rhetoric, and economic stress indicators."},
                    {"action": "update_threat_matrix", "detail": "Re-evaluate DEFCON/Warning levels based on new breakdown."},
                ],
            },
        ]

    def match(self, query: str) -> List[Dict]:
        q = query.lower()
        hits = []
        for pb in self.playbooks:
            if any(trigger in q for trigger in pb["triggers"]):
                hits.append(pb)
        return hits

    def build_response(self, playbooks: List[Dict], answer: str) -> Dict:
        return {
            "matched": [pb["id"] for pb in playbooks],
            "summary": [pb["description"] for pb in playbooks],
            "actions": [branch for pb in playbooks for branch in pb["branches"]],
            "answer_context": answer,
        }


playbook_store = PlaybookStore()

__all__ = ["PlaybookStore", "playbook_store"]
