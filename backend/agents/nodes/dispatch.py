from langgraph.constants import Send
from agents.state import InvestigationState, ERROR_CATEGORY_MAP, TECHNICAL_CATEGORIES, COMPLIANCE_CATEGORIES


def dispatch_node(state: InvestigationState) -> list:
    """Fan out to technical, compliance, or both based on error categories."""
    classification = state.get("intake_classification", {})
    needs_technical = classification.get("needs_technical", True)
    needs_compliance = classification.get("needs_compliance", False)

    targets = []
    if needs_technical:
        targets.append(Send("technical", state))
    if needs_compliance:
        targets.append(Send("compliance", state))
    return targets or [Send("technical", state)]
