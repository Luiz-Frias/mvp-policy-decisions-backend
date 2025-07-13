#!/usr/bin/env python3
"""
Compliance Models Demo - Examples of using the new Pydantic models.

This demonstrates how the new compliance models replace dict[str, Any] usage
throughout the compliance layer with proper type safety and validation.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.policy_core.schemas.compliance import (
    AccessControlMatrixResult,
    AuditLogEntry,
    AvailabilityMetrics,
    ComplianceReport,
    ComplianceStatus,
    ControlTestFinding,
    ControlTestResult,
    EvidenceItem,
    RiskLevel,
    SecurityAssessment,
    TrustServiceCriterion,
    VulnerabilityFinding,
    create_audit_log_entry,
    create_control_test_result,
    create_evidence_item,
)


def demo_audit_log_entry():
    """Demonstrate structured audit log entry instead of dict."""
    print("📋 AUDIT LOG ENTRY DEMO")
    print("=" * 50)

    # Before: dict[str, Any] with no validation
    # audit_data = {
    #     "event_type": "authentication",
    #     "action": "user_login",
    #     "user_id": "123e4567-e89b-12d3-a456-426614174000",
    #     "ip_address": "192.168.1.100",
    #     "risk_level": "medium",
    #     "request_method": "POST",
    #     "response_status": 200
    # }

    # After: Structured Pydantic model with validation
    audit_entry = create_audit_log_entry(
        event_type="authentication",
        action="user_login",
        user_id=uuid4(),
        ip_address="192.168.1.100",
        risk_level=RiskLevel.MEDIUM,
        request_method="POST",
        response_status=200,
        compliance_tags=["security", "authentication"],
        control_references=["SEC-001", "SEC-002"],
    )

    print(f"✅ Created audit entry: {audit_entry.action}")
    print(f"   Risk Level: {audit_entry.risk_level}")
    print(f"   Compliance Tags: {audit_entry.compliance_tags}")
    print(f"   Frozen/Immutable: {audit_entry.model_config.get('frozen', False)}")
    print()


def demo_control_test_result():
    """Demonstrate structured control test result instead of dict."""
    print("🔍 CONTROL TEST RESULT DEMO")
    print("=" * 50)

    # Before: Nested dicts with no type safety
    # test_result = {
    #     "test_result": "effective",
    #     "findings": [
    #         {
    #             "severity": "low",
    #             "description": "Minor configuration issue"
    #         }
    #     ],
    #     "evidence_collected": ["Configuration scan", "Manual review"],
    #     "execution_time_ms": 2500
    # }

    # After: Structured models with validation
    finding = ControlTestFinding(
        control_id="SEC-001",
        finding_type="configuration_issue",
        severity=RiskLevel.LOW,
        description="Minor configuration issue found during scan",
        impact="Low impact on security posture",
        likelihood="unlikely",
        remediation_required=False,
    )

    test_result = create_control_test_result(
        control_id="SEC-001",
        test_name="Data Encryption at Rest Verification",
        test_type="automated_testing",
        test_result="effective",
        executed_by="compliance_agent",
        trust_service_criteria=TrustServiceCriterion.SECURITY,
        effectiveness_score=95.5,
        findings=[finding],
        evidence_collected=["Configuration scan", "Manual review"],
        evidence_quality="adequate",
        conclusion="Control is operating effectively with minor improvements needed",
        execution_time_ms=2500,
    )

    print(f"✅ Created test result: {test_result.test_name}")
    print(f"   Result: {test_result.test_result}")
    print(f"   Effectiveness: {test_result.effectiveness_score}%")
    print(f"   Findings: {len(test_result.findings)}")
    print(f"   Evidence Quality: {test_result.evidence_quality}")
    print()


def demo_availability_metrics():
    """Demonstrate structured availability metrics instead of dict."""
    print("📊 AVAILABILITY METRICS DEMO")
    print("=" * 50)

    # Before: Dict with mixed types and no validation
    # metrics = {
    #     "uptime_percentage": 99.95,
    #     "downtime_minutes": 22,
    #     "sla_compliance": True,
    #     "response_time_p99": 125.5,
    #     "cpu_usage_percentage": 65.2
    # }

    # After: Structured model with precise types and validation
    metrics = AvailabilityMetrics(
        uptime_percentage=Decimal("99.95"),
        downtime_minutes=22,
        availability_sla=Decimal("99.9"),
        sla_compliance=True,
        incident_count=2,
        critical_incidents=0,
        mean_time_to_repair=11.0,
        mean_time_between_failures=720.0,
        response_time_p50=45.2,
        response_time_p95=89.1,
        response_time_p99=125.5,
        throughput_rps=234.5,
        error_rate_percentage=0.05,
        cpu_usage_percentage=65.2,
        memory_usage_percentage=72.8,
        disk_usage_percentage=45.3,
        measurement_period_start=datetime.now(timezone.utc),
        measurement_period_end=datetime.now(timezone.utc),
        measurement_period_hours=24,
    )

    print(f"✅ Created availability metrics")
    print(f"   Uptime: {metrics.uptime_percentage}%")
    print(f"   SLA Compliance: {metrics.sla_compliance}")
    print(f"   P99 Response Time: {metrics.response_time_p99}ms")
    print(f"   Error Rate: {metrics.error_rate_percentage}%")
    print()


def demo_security_assessment():
    """Demonstrate structured security assessment instead of dict."""
    print("🔒 SECURITY ASSESSMENT DEMO")
    print("=" * 50)

    # Before: Complex nested dict structure
    # assessment = {
    #     "vulnerabilities": [
    #         {
    #             "severity": "high",
    #             "component": "fastapi",
    #             "description": "Security vulnerability",
    #             "cvss_score": 7.5
    #         }
    #     ],
    #     "overall_risk_level": "medium",
    #     "compliance_status": "non_compliant"
    # }

    # After: Structured models with validation
    vulnerability = VulnerabilityFinding(
        vulnerability_id="CVE-2024-1234",
        cve_id="CVE-2024-1234",
        severity=RiskLevel.HIGH,
        component="fastapi",
        description="Potential security vulnerability in FastAPI",
        remediation="Upgrade to FastAPI 0.104.1 or later",
        cvss_score=7.5,
        exploitability="medium",
        patch_available=True,
        patch_version="0.104.1",
    )

    assessment = SecurityAssessment(
        assessment_type="vulnerability_scan",
        conducted_by="security_team",
        scope=["web_application", "api_endpoints"],
        coverage_percentage=98.5,
        vulnerabilities=[vulnerability],
        total_vulnerabilities=1,
        vulnerabilities_by_severity={"high": 1, "medium": 0, "low": 0},
        overall_risk_level=RiskLevel.MEDIUM,
        risk_score=65.0,
        compliance_status=ComplianceStatus.NON_COMPLIANT,
        compliance_score=75.0,
        remediation_required=True,
        remediation_timeline="30 days",
        priority_actions=["Upgrade FastAPI", "Review security configuration"],
    )

    print(f"✅ Created security assessment")
    print(f"   Risk Level: {assessment.overall_risk_level}")
    print(f"   Compliance: {assessment.compliance_status}")
    print(f"   Vulnerabilities: {assessment.total_vulnerabilities}")
    print(f"   Coverage: {assessment.coverage_percentage}%")
    print()


def demo_evidence_collection():
    """Demonstrate structured evidence collection instead of dict."""
    print("📄 EVIDENCE COLLECTION DEMO")
    print("=" * 50)

    # Before: Dict with no structure or validation
    # evidence = {
    #     "evidence_type": "control_testing",
    #     "title": "Encryption Control Test",
    #     "data_source": "automated_scan",
    #     "reliability": "high",
    #     "storage_location": "evidence_vault"
    # }

    # After: Structured evidence model
    evidence = create_evidence_item(
        evidence_type="control_testing",
        title="Encryption Control Test Results",
        description="Results from automated encryption control testing",
        control_id="SEC-001",
        trust_service_criteria=TrustServiceCriterion.SECURITY,
        evidence_period_start=datetime.now(timezone.utc),
        evidence_period_end=datetime.now(timezone.utc),
        data_source="automated_scan",
        collection_method="system_query",
        reliability="high",
        completeness="complete",
        relevance="directly_relevant",
        storage_location="evidence_vault",
        retention_period_days=2555,
        collector="compliance_system",
        approval_status="approved",
    )

    print(f"✅ Created evidence item: {evidence.title}")
    print(f"   Type: {evidence.evidence_type}")
    print(f"   Reliability: {evidence.reliability}")
    print(f"   Completeness: {evidence.completeness}")
    print(f"   Retention: {evidence.retention_period_days} days")
    print()


def demo_compliance_report():
    """Demonstrate structured compliance report instead of dict."""
    print("📋 COMPLIANCE REPORT DEMO")
    print("=" * 50)

    # Before: Complex nested dict structure
    # report = {
    #     "overall_compliance_status": "compliant",
    #     "compliance_score": 95.5,
    #     "findings_by_severity": {"high": 0, "medium": 2, "low": 5},
    #     "trust_service_criteria": ["security", "availability"]
    # }

    # After: Structured report model
    report = ComplianceReport(
        report_type="soc2_type_ii",
        report_title="SOC 2 Type II Compliance Assessment",
        assessment_period_start=datetime.now(timezone.utc),
        assessment_period_end=datetime.now(timezone.utc),
        trust_service_criteria=[
            TrustServiceCriterion.SECURITY,
            TrustServiceCriterion.AVAILABILITY,
        ],
        overall_compliance_status=ComplianceStatus.COMPLIANT,
        overall_compliance_score=95.5,
        total_findings=7,
        findings_by_severity={"high": 0, "medium": 2, "low": 5},
        management_recommendations=[
            "Continue current security practices",
            "Implement additional monitoring",
        ],
        technical_recommendations=[
            "Upgrade vulnerable components",
            "Enhance logging capabilities",
        ],
        generated_by="compliance_team",
        distribution_list=["management", "audit_committee"],
        confidentiality_level="confidential",
    )

    print(f"✅ Created compliance report: {report.report_title}")
    print(f"   Status: {report.overall_compliance_status}")
    print(f"   Score: {report.overall_compliance_score}%")
    print(f"   Findings: {report.total_findings}")
    print(f"   Criteria: {len(report.trust_service_criteria)}")
    print()


def main():
    """Run all compliance model demos."""
    print("🚀 COMPLIANCE MODELS DEMONSTRATION")
    print("=" * 60)
    print("This demo shows how Pydantic models replace dict[str, Any] usage")
    print("throughout the compliance layer with type safety and validation.")
    print()

    demo_audit_log_entry()
    demo_control_test_result()
    demo_availability_metrics()
    demo_security_assessment()
    demo_evidence_collection()
    demo_compliance_report()

    print("✅ ALL DEMOS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("Benefits of structured models:")
    print("• Type safety with beartype and mypy")
    print("• Immutable data structures (frozen=True)")
    print("• Automatic validation and serialization")
    print("• Clear API contracts and documentation")
    print("• IDE support with autocomplete")
    print("• Easier testing and debugging")


if __name__ == "__main__":
    main()
