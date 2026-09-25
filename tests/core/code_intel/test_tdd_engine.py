import pytest
from titan_agent.core.code_intel.tdd_engine import AutonomousTDDEngine


@pytest.mark.asyncio
async def test_tdd_engine_full_successful_cycle(tmp_path):
    engine = AutonomousTDDEngine(workspace_root=tmp_path)

    test_code = """
import pytest
from feature import calculate_discount

def test_calculate_discount():
    assert calculate_discount(100.0, 0.2) == 80.0
    assert calculate_discount(50.0, 0.5) == 25.0
"""

    implementation_code = """
def calculate_discount(price: float, discount: float) -> float:
    return price * (1.0 - discount)
"""

    report = await engine.execute_tdd_cycle(
        test_code=test_code,
        implementation_code=implementation_code,
        test_filename="test_feature.py",
        code_filename="feature.py",
        timeout=15.0,
    )

    assert report.full_cycle_success is True
    assert report.red_stage.success is True  # Failed on initial stub
    assert report.green_stage.success is True  # Passed on implementation
    assert report.refactor_stage.success is True  # Symbolic invariants sound
    assert "PASSED" in report.format_text()


@pytest.mark.asyncio
async def test_tdd_engine_fails_on_broken_implementation(tmp_path):
    engine = AutonomousTDDEngine(workspace_root=tmp_path)

    test_code = """
def test_multiply():
    from feature import multiply
    assert multiply(3, 4) == 12
"""

    # Flawed implementation
    implementation_code = """
def multiply(a: int, b: int) -> int:
    return a + b  # Bug: returns addition instead of multiplication
"""

    report = await engine.execute_tdd_cycle(
        test_code=test_code,
        implementation_code=implementation_code,
        test_filename="test_feature.py",
        code_filename="feature.py",
        timeout=15.0,
    )

    assert report.full_cycle_success is False
    assert report.red_stage.success is True  # Failed initially
    assert report.green_stage.success is False  # Implementation also failed


@pytest.mark.asyncio
async def test_tdd_engine_fails_on_symbolic_invariant_hazard(tmp_path):
    engine = AutonomousTDDEngine(workspace_root=tmp_path)

    test_code = """
def test_dangerous():
    from feature import do_danger
    assert do_danger("ls") == 0
"""

    # Has shell injection hazard
    implementation_code = """
import subprocess
def do_danger(arg):
    return subprocess.run(f"echo {arg}", shell=True).returncode
"""

    report = await engine.execute_tdd_cycle(
        test_code=test_code,
        implementation_code=implementation_code,
        test_filename="test_feature.py",
        code_filename="feature.py",
        timeout=15.0,
    )

    # Even if pytest passed or failed, refactor phase must detect symbolic violation
    assert report.refactor_stage.success is False
    assert report.full_cycle_success is False
