
from app.reasoning.legal_reasoning_engine import LegalReasoningEngine
from app.reasoning.explainability_engine import ExplainabilityEngine
from app.reasoning.logical_validator import LogicalValidator

class ReasoningPipeline:

    def __init__(self):

        self.reasoner = LegalReasoningEngine()
        self.explainer = ExplainabilityEngine()
        self.validator = LogicalValidator()

    def execute(self, process_state):

        reasoning = self.reasoner.analyse(process_state)

        explanation = self.explainer.explain(reasoning)

        validation = self.validator.validate(reasoning)

        return {
            "reasoning": reasoning,
            "explanation": explanation,
            "validation": validation
        }
