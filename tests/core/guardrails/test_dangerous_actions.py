import pytest
from titan_agent.core.guardrails.dangerous_actions import (
    DangerousActionClassifier,
    DangerousActionGate,
)
from titan_agent.core.guardrails.hitl import ApprovalStatus, HumanInTheLoop


def test_dangerous_action_classifier_detects_force_push():
    assessment = DangerousActionClassifier.assess_action(
        "execute_command",
        details={"command": "git push origin main --force"},
    )
    assert assessment.is_dangerous is True
    assert assessment.risk_level == "CRITICAL"
    assert "git_force_push" in assessment.category
    assert "Do you authorize this action? [Yes / No]" in assessment.suggested_prompt


def test_dangerous_action_classifier_detects_rm_rf():
    assessment = DangerousActionClassifier.assess_action(
        "execute_command",
        details={"command": "rm -rf /var/data/important"},
    )
    assert assessment.is_dangerous is True
    assert assessment.risk_level == "CRITICAL"
    assert "recursive_file_deletion" in assessment.category


def test_dangerous_action_classifier_detects_env_edit():
    assessment = DangerousActionClassifier.assess_action(
        "edit_file",
        resource=".env",
    )
    assert assessment.is_dangerous is True
    assert assessment.risk_level == "HIGH"
    assert "sensitive_file_modification" in assessment.category
    assert "Do you authorize this action? [Yes / No]" in assessment.suggested_prompt


def test_safe_action_passes_without_flag():
    assessment = DangerousActionClassifier.assess_action(
        "read_file",
        resource="main.py",
        details={"command": "ls -l"},
    )
    assert assessment.is_dangerous is False
    assert assessment.risk_level == "LOW"


@pytest.mark.asyncio
async def test_dangerous_action_gate_approval_flow():
    hitl = HumanInTheLoop()
    gate = DangerousActionGate(hitl)

    # Approve flow simulation
    async def _auto_approve():
        import asyncio
        await asyncio.sleep(0.05)
        # Find pending request and approve it
        for req in list(hitl._requests.values()):
            if req.status == ApprovalStatus.PENDING:
                hitl.approve(req.request_id, by="admin")

    import asyncio
    approve_task = asyncio.create_task(_auto_approve())
    ok, msg = await gate.check_and_gate("execute_command", details={"command": "git push origin main --force"}, timeout=5.0)
    await approve_task

    assert ok is True
    assert "approved by human" in msg.lower()
