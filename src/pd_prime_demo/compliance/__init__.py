"""SOC 2 Type II Compliance Framework.

This module provides comprehensive SOC 2 compliance controls covering all five trust service criteria:
1. Security Controls
2. Availability Controls
3. Processing Integrity Controls
4. Confidentiality Controls
5. Privacy Controls

The framework implements enterprise-grade compliance automation, evidence collection,
and continuous monitoring to meet SOC 2 Type II requirements.
"""

from .audit_logger import AuditLogger, ComplianceEvent
from .availability_controls import AvailabilityControlManager
from .confidentiality_controls import ConfidentialityControlManager
from .control_framework import (
    SOC2_CORE_CONTROLS,
    ControlFramework,
    ControlType,
    TrustServiceCriteria,
)
from .control_testing import ControlTestingFramework, get_testing_framework
from .evidence_collector import EvidenceCollector, EvidenceType, get_evidence_collector
from .privacy_controls import PrivacyControlManager
from .processing_integrity import ProcessingIntegrityManager
from .security_controls import SecurityControlManager

__all__ = [
    "AuditLogger",
    "ComplianceEvent",
    "ControlFramework",
    "ControlType",
    "TrustServiceCriteria",
    "SOC2_CORE_CONTROLS",
    "ControlTestingFramework",
    "get_testing_framework",
    "EvidenceCollector",
    "EvidenceType",
    "get_evidence_collector",
    "SecurityControlManager",
    "AvailabilityControlManager",
    "ProcessingIntegrityManager",
    "ConfidentialityControlManager",
    "PrivacyControlManager",
]
