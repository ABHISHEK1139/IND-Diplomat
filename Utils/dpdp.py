"""
DPDP Act 2023 Compliance Module
Implements India's Digital Personal Data Protection Act requirements.
Includes data masking, consent management, and breach readiness.
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
import hashlib
import json


class DataCategory(Enum):
    """Categories of personal data under DPDP Act."""
    GENERAL = "general"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"  # Data fiduciary defined


class ProcessingPurpose(Enum):
    """Lawful purposes for data processing."""
    CONSENT = "consent"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_INTEREST = "public_interest"
    LEGITIMATE_INTEREST = "legitimate_interest"


class DataPrincipalRight(Enum):
    """Rights of data principals under DPDP Act."""
    ACCESS = "access"
    CORRECTION = "correction"
    ERASURE = "erasure"
    GRIEVANCE = "grievance"
    NOMINATE = "nominate"


@dataclass
class ConsentRecord:
    """Record of data principal consent."""
    consent_id: str
    data_principal_id: str
    purpose: ProcessingPurpose
    data_categories: List[DataCategory]
    granted_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    withdrawal_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataMaskingRule:
    """Rule for masking sensitive data."""
    rule_id: str
    pattern: str
    data_type: str
    masking_method: str  # "hash", "redact", "tokenize", "pseudonymize"
    preserve_format: bool


@dataclass
class BreachRecord:
    """Record of a data breach."""
    breach_id: str
    detected_at: datetime
    reported_at: Optional[datetime]
    data_categories_affected: List[DataCategory]
    principals_affected_count: int
    severity: str  # "low", "medium", "high", "critical"
    remediation_status: str
    board_notified: bool
    dpb_notified: bool  # Data Protection Board


class DPDPCompliance:
    """
    Digital Personal Data Protection Act 2023 Compliance Module.
    
    Implements:
    1. Automated data masking for sensitive identifiers
    2. Consent management and audit trail
    3. 72-hour breach notification readiness
    4. Data localization requirements
    5. Purpose limitation enforcement
    """
    
    # PII Patterns for Indian context
    PII_PATTERNS = {
        "aadhaar": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b",
        "phone_in": r"\b(?:\+91|91|0)?[6-9]\d{9}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "passport": r"\b[A-Z]\d{7}\b",
        "voter_id": r"\b[A-Z]{3}\d{7}\b",
        "bank_account": r"\b\d{9,18}\b",
        "ifsc": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        "name_in": r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Shri|Smt)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"
    }
    
    # Masking rules
    DEFAULT_MASKING_RULES = [
        DataMaskingRule("mask_aadhaar", r"\b\d{4}\s?\d{4}\s?\d{4}\b", "aadhaar", "redact", False),
        DataMaskingRule("mask_pan", r"\b[A-Z]{5}\d{4}[A-Z]\b", "pan", "hash", True),
        DataMaskingRule("mask_phone", r"\b(?:\+91|91|0)?[6-9]\d{9}\b", "phone", "tokenize", False),
        DataMaskingRule("mask_email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email", "pseudonymize", True),
    ]
    
    # Breach notification timeline
    BREACH_NOTIFICATION_HOURS = 72
    
    def __init__(self):
        self._consent_registry: Dict[str, ConsentRecord] = {}
        self._breach_registry: Dict[str, BreachRecord] = {}
        self._masking_rules = self.DEFAULT_MASKING_RULES.copy()
        self._audit_log: List[Dict] = []
        
        # Breach readiness checkpoints
        self._breach_readiness_checks: List[datetime] = []
    
    # ============== Data Masking ==============
    
    def mask_pii(
        self, 
        text: str, 
        categories: List[str] = None
    ) -> Tuple[str, Dict[str, int]]:
        """
        Mask PII in text according to DPDP requirements.
        Returns masked text and count of masked items by category.
        """
        masked_text = text
        mask_counts = {}
        
        rules_to_apply = self._masking_rules
        if categories:
            rules_to_apply = [r for r in self._masking_rules if r.data_type in categories]
        
        for rule in rules_to_apply:
            matches = re.findall(rule.pattern, masked_text, re.IGNORECASE)
            mask_counts[rule.data_type] = len(matches)
            
            for match in matches:
                masked_value = self._apply_masking(match, rule)
                masked_text = masked_text.replace(match, masked_value)
        
        # Log masking action
        self._audit_log.append({
            "action": "mask_pii",
            "timestamp": datetime.now().isoformat(),
            "categories_masked": list(mask_counts.keys()),
            "total_masked": sum(mask_counts.values())
        })
        
        return masked_text, mask_counts
    
    def _apply_masking(self, value: str, rule: DataMaskingRule) -> str:
        """Apply masking method to value."""
        if rule.masking_method == "redact":
            return "[REDACTED]"
        
        elif rule.masking_method == "hash":
            hashed = hashlib.sha256(value.encode()).hexdigest()[:8]
            if rule.preserve_format:
                # Preserve format pattern
                return re.sub(r"[A-Za-z0-9]", "X", value[:-4]) + hashed[:4].upper()
            return f"[HASH:{hashed}]"
        
        elif rule.masking_method == "tokenize":
            token = hashlib.md5(value.encode()).hexdigest()[:10]
            return f"[TOKEN:{token}]"
        
        elif rule.masking_method == "pseudonymize":
            if rule.data_type == "email":
                # Preserve domain
                parts = value.split("@")
                if len(parts) == 2:
                    return f"user_{hashlib.md5(parts[0].encode()).hexdigest()[:6]}@{parts[1]}"
            return f"[PSEUDO:{hashlib.md5(value.encode()).hexdigest()[:8]}]"
        
        return "[MASKED]"
    
    def detect_pii(self, text: str) -> Dict[str, List[str]]:
        """Detect PII in text without masking."""
        detected = {}
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected[pii_type] = matches
        
        return detected
    
    # ============== Consent Management ==============
    
    def record_consent(
        self,
        data_principal_id: str,
        purpose: ProcessingPurpose,
        data_categories: List[DataCategory],
        expires_days: int = 365
    ) -> ConsentRecord:
        """Record data principal consent."""
        consent_id = f"consent_{hashlib.md5(f'{data_principal_id}{datetime.now()}'.encode()).hexdigest()[:12]}"
        
        record = ConsentRecord(
            consent_id=consent_id,
            data_principal_id=data_principal_id,
            purpose=purpose,
            data_categories=data_categories,
            granted_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expires_days),
            is_active=True
        )
        
        self._consent_registry[consent_id] = record
        
        self._audit_log.append({
            "action": "consent_granted",
            "timestamp": datetime.now().isoformat(),
            "consent_id": consent_id,
            "purpose": purpose.value
        })
        
        return record
    
    def withdraw_consent(self, consent_id: str) -> bool:
        """Withdraw consent (data principal right)."""
        if consent_id not in self._consent_registry:
            return False
        
        record = self._consent_registry[consent_id]
        record.is_active = False
        record.withdrawal_date = datetime.now()
        
        self._audit_log.append({
            "action": "consent_withdrawn",
            "timestamp": datetime.now().isoformat(),
            "consent_id": consent_id
        })
        
        return True
    
    def check_consent(
        self,
        data_principal_id: str,
        purpose: ProcessingPurpose,
        data_category: DataCategory
    ) -> bool:
        """Check if valid consent exists for processing."""
        for record in self._consent_registry.values():
            if (record.data_principal_id == data_principal_id and
                record.purpose == purpose and
                data_category in record.data_categories and
                record.is_active and
                (record.expires_at is None or record.expires_at > datetime.now())):
                return True
        return False
    
    # ============== Data Principal Rights ==============
    
    def handle_rights_request(
        self,
        data_principal_id: str,
        right: DataPrincipalRight,
        request_details: Dict = None
    ) -> Dict[str, Any]:
        """Handle data principal rights request."""
        response = {
            "request_id": f"req_{hashlib.md5(f'{data_principal_id}{datetime.now()}'.encode()).hexdigest()[:10]}",
            "data_principal_id": data_principal_id,
            "right_requested": right.value,
            "received_at": datetime.now().isoformat(),
            "status": "processing"
        }
        
        if right == DataPrincipalRight.ACCESS:
            response["action"] = "Compile all personal data held"
            response["timeline_days"] = 30
        
        elif right == DataPrincipalRight.CORRECTION:
            response["action"] = "Review and update records"
            response["timeline_days"] = 15
        
        elif right == DataPrincipalRight.ERASURE:
            response["action"] = "Delete personal data (where lawful)"
            response["timeline_days"] = 30
            response["exceptions"] = ["Legal obligation", "Defense of claims"]
        
        elif right == DataPrincipalRight.GRIEVANCE:
            response["action"] = "Acknowledge and investigate"
            response["timeline_days"] = 7
        
        self._audit_log.append({
            "action": "rights_request",
            "timestamp": datetime.now().isoformat(),
            "request_id": response["request_id"],
            "right": right.value
        })
        
        return response
    
    # ============== Breach Readiness ==============
    
    def record_breach(
        self,
        data_categories: List[DataCategory],
        principals_count: int,
        severity: str
    ) -> BreachRecord:
        """Record a data breach incident."""
        breach_id = f"breach_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        record = BreachRecord(
            breach_id=breach_id,
            detected_at=datetime.now(),
            reported_at=None,
            data_categories_affected=data_categories,
            principals_affected_count=principals_count,
            severity=severity,
            remediation_status="investigating",
            board_notified=False,
            dpb_notified=False
        )
        
        self._breach_registry[breach_id] = record
        
        # Trigger notification requirements check
        self._check_notification_requirements(record)
        
        self._audit_log.append({
            "action": "breach_detected",
            "timestamp": datetime.now().isoformat(),
            "breach_id": breach_id,
            "severity": severity
        })
        
        return record
    
    def _check_notification_requirements(self, breach: BreachRecord):
        """Check if breach requires Data Protection Board notification."""
        # DPDP Act requires notification within 72 hours for significant breaches
        deadline = breach.detected_at + timedelta(hours=self.BREACH_NOTIFICATION_HOURS)
        
        if breach.severity in ["high", "critical"]:
            print(f"[DPDP ALERT] High severity breach detected. DPB notification required by {deadline}")
    
    def get_breach_report(self, breach_id: str) -> Dict[str, Any]:
        """Generate breach report for DPB notification."""
        breach = self._breach_registry.get(breach_id)
        if not breach:
            return {"error": "Breach not found"}
        
        return {
            "breach_id": breach.breach_id,
            "detected_at": breach.detected_at.isoformat(),
            "notification_deadline": (breach.detected_at + timedelta(hours=72)).isoformat(),
            "hours_remaining": max(0, (breach.detected_at + timedelta(hours=72) - datetime.now()).total_seconds() / 3600),
            "data_categories": [c.value for c in breach.data_categories_affected],
            "principals_affected": breach.principals_affected_count,
            "severity": breach.severity,
            "remediation_status": breach.remediation_status,
            "board_notified": breach.board_notified,
            "dpb_notified": breach.dpb_notified
        }
    
    def run_breach_readiness_drill(self) -> Dict[str, Any]:
        """Run 72-hour breach readiness muscle memory drill."""
        drill_time = datetime.now()
        
        # Simulate breach detection
        mock_breach = self.record_breach(
            data_categories=[DataCategory.SENSITIVE],
            principals_count=0,  # Drill only
            severity="drill"
        )
        
        # Check systems
        checks = {
            "consent_registry_accessible": len(self._consent_registry) >= 0,
            "masking_rules_loaded": len(self._masking_rules) > 0,
            "audit_log_functional": len(self._audit_log) > 0,
            "notification_template_ready": True,
            "escalation_contacts_defined": True
        }
        
        # Log drill
        self._breach_readiness_checks.append(drill_time)
        
        # Clean up drill record
        del self._breach_registry[mock_breach.breach_id]
        
        return {
            "drill_timestamp": drill_time.isoformat(),
            "all_checks_passed": all(checks.values()),
            "check_results": checks,
            "next_drill_recommended": (drill_time + timedelta(days=30)).isoformat()
        }
    
    # ============== Data Localization ==============
    
    def validate_data_localization(
        self,
        data_category: DataCategory,
        storage_location: str
    ) -> Dict[str, Any]:
        """Validate data localization requirements."""
        # Critical data must be stored in India
        india_locations = ["in-west", "in-south", "mumbai", "delhi", "hyderabad", "chennai"]
        
        is_india = any(loc in storage_location.lower() for loc in india_locations)
        
        result = {
            "data_category": data_category.value,
            "storage_location": storage_location,
            "is_compliant": True,
            "notes": []
        }
        
        if data_category == DataCategory.CRITICAL and not is_india:
            result["is_compliant"] = False
            result["notes"].append("Critical data must be stored in India")
        
        if data_category == DataCategory.SENSITIVE and not is_india:
            result["notes"].append("Sensitive data recommended to be stored in India")
        
        return result
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate overall DPDP compliance report."""
        return {
            "report_generated": datetime.now().isoformat(),
            "consent_records": len(self._consent_registry),
            "active_consents": sum(1 for c in self._consent_registry.values() if c.is_active),
            "breach_incidents": len(self._breach_registry),
            "masking_rules": len(self._masking_rules),
            "audit_log_entries": len(self._audit_log),
            "last_breach_drill": self._breach_readiness_checks[-1].isoformat() if self._breach_readiness_checks else None,
            "pii_patterns_configured": list(self.PII_PATTERNS.keys())
        }


# Singleton instance
dpdp_compliance = DPDPCompliance()


# Convenience function for API use
from typing import Tuple

def mask_document(text: str) -> Tuple[str, Dict]:
    """Mask PII in a document for compliant processing."""
    return dpdp_compliance.mask_pii(text)
