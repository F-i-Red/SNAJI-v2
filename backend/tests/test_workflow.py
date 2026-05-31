
from app.workflow.workflow_engine import WorkflowEngine

def test_workflow():

    workflow = WorkflowEngine()

    result = workflow.next_stage({})

    assert result["next_stage"] == "review"
