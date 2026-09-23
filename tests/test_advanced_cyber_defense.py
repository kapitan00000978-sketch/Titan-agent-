"""Tests for Advanced Cyber Defense Capabilities: SAST, Secret Scanning, Dependency Auditing & Threat Modeling."""

from titan_agent.commands import expand_slash
from titan_agent.core.security.dependency_auditor import DependencyAuditor
from titan_agent.core.security.sast import SASTScanner
from titan_agent.core.security.secret_scanner import SecretScanner
from titan_agent.core.security.threat_model import ThreatModelEngine
from titan_agent.tools import ToolRegistry


def test_secret_scanner_detection_and_redaction():
    scanner = SecretScanner()
    # 1. AWS Key
    text = "Deploy config: AWS_KEY=AKIAIOSFODNN7EXAMPLE and SECRET=sk-proj-1234567890abcdef1234567890abcdef1234567890"
    findings = scanner.scan(text)
    assert len(findings) >= 2
    types = {f.secret_type for f in findings}
    assert "AWS Access Key" in types
    assert "OpenAI/Anthropic API Key" in types

    # 2. Entropy
    assert SecretScanner.shannon_entropy("AAAAAA") < 1.0
    assert SecretScanner.shannon_entropy("a8F9#kL2!pQ9$zX1") > 3.5

    # 3. Redaction
    redacted = scanner.redact(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "REDACTED" in redacted


def test_sast_scanner_owasp_vulnerabilities():
    scanner = SASTScanner()
    code = """
import pickle
import subprocess

def handler(user_query, user_path):
    cursor.execute(f"SELECT * FROM users WHERE name = '%s'" % user_query)
    subprocess.Popen("ls " + user_path, shell=True)
    obj = pickle.loads(user_query)
    eval("print('hello')")
"""
    report = scanner.scan_code(code, "test_handler.py")
    assert report.total_findings >= 3
    assert report.critical_count >= 1
    rule_ids = {f.rule_id for f in report.findings}
    assert "SEC-INJ-001" in rule_ids  # SQL Injection
    assert "SEC-INJ-002" in rule_ids  # Shell=True
    assert "SEC-DESER-001" in rule_ids  # Pickle loads
    assert "SEC-DYN-001" in rule_ids  # Dynamic eval


def test_dependency_auditor():
    auditor = DependencyAuditor()
    reqs = """
# Production requirements
urllib3==1.26.15
requests==2.28.0
aiohttp==3.9.0
http://insecure-mirror.local/pkg/custom.whl
"""
    report = auditor.audit_requirements_text(reqs, "requirements.txt")
    assert report.total_dependencies >= 4
    assert report.vulnerable_count >= 3
    packages = {a.package for a in report.alerts}
    assert "urllib3" in packages
    assert "aiohttp" in packages


def test_threat_model_engine_forensic_report():
    engine = ThreatModelEngine()
    report = engine.generate_forensic_report(
        incident_id="INC-TEST-001",
        vector_key="command_injection",
        payload_sample="rm -rf /",
        detection_reasons=["Root-level Destructive Deletion"],
        containment_status="CONTAINED",
    )
    assert "INC-TEST-001" in report
    assert "T1059.004" in report
    assert "Execution (TA0002)" in report
    assert "CONTAINED" in report


def test_security_tools_in_registry(tmp_path):
    tools = ToolRegistry(workspace=tmp_path)
    
    # 1. SAST Tool
    sast_res = tools.tool_sast_scan("eval('1+1')", "script.py")
    assert "SAST & OWASP Security Report" in sast_res

    # 2. Secret Scan Tool
    sec_res = tools.tool_secret_scan("ghp_1234567890abcdef1234567890abcdef1234")
    assert "Secret Scanner Alert" in sec_res

    # 3. Dependency Audit Tool
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("urllib3==1.26.10\n", encoding="utf-8")
    dep_res = tools.tool_dependency_audit("requirements.txt")
    assert "Supply-Chain Dependency Audit" in dep_res


def test_new_security_slash_commands():
    sast_cmd = expand_slash("/sast main.py")
    assert sast_cmd is not None
    assert sast_cmd["command"] == "sast"
    assert "sast_scan" in sast_cmd["prompt"]

    deps_cmd = expand_slash("/deps-audit requirements.txt")
    assert deps_cmd is not None
    assert deps_cmd["command"] == "deps-audit"
    assert "dependency_audit" in deps_cmd["prompt"]

    sec_cmd = expand_slash("/secret-scan config.env")
    assert sec_cmd is not None
    assert sec_cmd["command"] == "secret-scan"
    assert "secret_scan" in sec_cmd["prompt"]
