"""Unit tests for SymbolicInvariantChecker."""
import pytest
from titan_agent.core.code_intel.symbolic_checker import (
    SymbolicInvariantChecker,
    ViolationSeverity,
)


def test_clean_code_passes():
    code = """
def compute_sum(items):
    total = 0
    for x in items:
        total += x
    return total
"""
    report = SymbolicInvariantChecker.check_code(code)
    assert report.is_safe is True
    assert report.violations_count == 0


def test_infinite_loop_detected():
    code = """
def bad_loop():
    while True:
        print("hanging forever")
"""
    report = SymbolicInvariantChecker.check_code(code)
    assert report.is_safe is False
    assert report.critical_count >= 1
    assert any(v.invariant_id == "INV001_INFINITE_LOOP" for v in report.violations)


def test_shell_injection_detected():
    code = """
import subprocess
def run_user_cmd(user_arg):
    subprocess.run(f"echo {user_arg}", shell=True)
"""
    report = SymbolicInvariantChecker.check_code(code)
    assert report.is_safe is False
    assert any(v.invariant_id == "INV002_SHELL_INJECTION" for v in report.violations)


def test_resource_leak_detected():
    code = """
def read_log():
    f = open("log.txt")
    data = f.read()
    return data
"""
    report = SymbolicInvariantChecker.check_code(code)
    assert any(v.invariant_id == "INV004_RESOURCE_LEAK" for v in report.violations)
