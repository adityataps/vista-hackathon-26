import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import InvestigationState
from agents.tools.payment_tools import get_payment_record

logger = logging.getLogger(__name__)

SYSTEM = """You are the Investigation Agent. You gather context about a payment before
specialist agents investigate. Summarise the key payment details in 1-2 sentences:
amount, corridor, sender, receiver, and what makes this payment notable."""


async def investigate_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    payment = state["payment"]
    summary_prompt = (
        f"Payment msg_id={payment.get('msg_id')} "
        f"amount={payment.get('amount')} {payment.get('currency')} "
        f"sender={payment.get('debtor_name')} ({payment.get('sender_bic')}) "
        f"receiver={payment.get('creditor_name')} ({payment.get('receiver_bic')}) "
        f"errors={json.dumps(state['detected_errors'])}. "
        "Summarise this payment and the detected errors in 1-2 sentences."
    )
    response = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=summary_prompt)])
    summary = response.content

    ts = datetime.now(timezone.utc).isoformat()
    step = {"agent": "Investigation Agent", "cls": "investigation", "text": summary, "ts": ts}

    context = {
        "debtor_iban": payment.get("debtor_iban"),
        "creditor_iban": payment.get("creditor_iban"),
        "debtor_bic": payment.get("debtor_bic"),
        "creditor_bic": payment.get("creditor_bic"),
        "debtor_name": payment.get("debtor_name"),
        "creditor_name": payment.get("creditor_name"),
        "amount": str(payment.get("amount")),
        "currency": payment.get("currency"),
        "uetr": payment.get("uetr"),
    }

    return {
        "investigation_context": context,
        "steps": state.get("steps", []) + [step],
    }
