
from app.workflow.approval_system import ApprovalSystem

def test_approval():

    approval = ApprovalSystem()

    result = approval.approve(
        "admin",
        "P-001"
    )

    assert result["approved"]
