import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import InvestigationState
from agents.tools.payment_tools import get_resolution_history

logger = logging.getLogger(__name__)

SYSTEM = """You are the Resolution Agent. You synthesise findings from specialist agents
and produce a single clear recommendation for the human analyst.
Your output must be a JSON object with exactly these keys:
  action   — one sentence: what the analyst should do
  rationale — 2-3 sentences: why, citing specific evidence from the investigation
  confidence — a float 0.0–1.0

Do NOT recommend any autonomous action. Always end with the analyst making the final decision."""


async def resolution_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    technical = state.get("technical_findings") or {}
    compliance = state.get("compliance_findings") or {}
    errors = state["detected_errors"]

    # pull resolution history for context
    error_codes = [e.get("code") for e in errors if e.get("code")]
    history_results = []
    for code in error_codes[:2]:  # limit to 2 lookups
        history_results.append(get_resolution_history.invoke({"error_code": code}))

    prompt = (
        f"Technical findings:\n{technical.get('raw', 'N/A')}\n\n"
        f"Compliance findings:\n{compliance.get('raw', 'N/A')}\n\n"
        f"Prior resolution history:\n{json.dumps(history_results)}\n\n"
        "Synthesise these findings and produce your recommendation as a JSON object with "
        "keys: action, rationale, confidence."
    )

    response = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])
    raw = response.content.strip()

    # extract JSON — model may wrap in markdown code block
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        recommendation = json.loads(raw)
    except Exception:
        recommendation = {"action": raw, "rationale": "See full agent output.", "confidence": 0.8}

    ts = datetime.now(timezone.utc).isoformat()
    step = {
        "agent": "Resolution Agent",
        "cls": "resolution",
        "text": f"Recommendation: {recommendation.get('action', '')} (confidence {recommendation.get('confidence', 0):.0%})",
        "ts": ts,
    }

    return {
        "recommendation": recommendation,
        "steps": state.get("steps", []) + [step],
    }
