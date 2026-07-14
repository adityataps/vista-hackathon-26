"""Generates realistic payment processing event chains for pacs.008 messages.

Events model the PAYplus / SWIFT CBPR+ processing pipeline from message
receipt through settlement or exception routing.  Event IDs are derived from
msg_id (not UETR) so DUPLICATE_UETR injections never produce ID collisions.
Timestamps are anchored to the message creation time with realistic offsets.
"""
import datetime
import uuid

# (status_code, source_system, actor) per event type
_SYSTEMS = {
    "PAYMENT_RECEIVED":           ("RCVD", "SWIFT_GATEWAY",      "GW-PAYplus-PROD-1"),
    "FORMAT_VALIDATED":           ("ACTC", "FORMAT_VALIDATOR",   "FMT-CHK-v2.3"),
    "SANCTIONS_CLEARED":          ("ACSP", "SANCTIONS_SCREEN",   "SanctionsSvc-OFAC-EU"),
    "SANCTIONS_HIT":              ("HOLD", "SANCTIONS_SCREEN",   "SanctionsSvc-OFAC-EU"),
    "DUPLICATE_DETECTED":         ("HOLD", "DUPLICATE_CHECKER",  "DUP-DETECT-v1"),
    "BUSINESS_VALIDATION_FAILED": ("RJCT", "BUSINESS_VALIDATOR", "BIZ-RULE-ENGINE"),
    "ROUTING_RESOLVED":           ("ACSP", "ROUTING_ENGINE",     "ROUTING-PAYplus"),
    "SETTLEMENT_INITIATED":       ("ACSP", "SETTLEMENT_ENGINE",  "STTLM-ENGINE"),
    "CORRESPONDENT_ACK":          ("ACSP", "SETTLEMENT_ENGINE",  "STTLM-ENGINE"),
    "SETTLEMENT_CONFIRMED":       ("ACCC", "SETTLEMENT_ENGINE",  "STTLM-ENGINE"),
    "PROCESSING_DELAYED":         ("ACWP", "SETTLEMENT_ENGINE",  "STTLM-ENGINE"),
    "PAYMENT_HELD":               ("HOLD", "EXCEPTION_MANAGER",  "EXC-MGR-PAYplus"),
    "EXCEPTION_RAISED":           ("RJCT", "EXCEPTION_MANAGER",  "EXC-MGR-PAYplus"),
}

_SANCTIONS_CODES  = {"SANCTIONS_NAME_HIT"}
_COMPLIANCE_CODES = {"ADDRESS_INCOMPLETE", "BENEFICIARY_NAME_INCOMPLETE"}
_ACCOUNT_CODES    = {"IBAN_INVALID_CHECKSUM", "IBAN_WRONG_LENGTH", "ACCOUNT_CLOSED"}
_ROUTING_CODES    = {"BIC_UNKNOWN", "BIC_INVALID_COUNTRY", "BIC_IBAN_COUNTRY_MISMATCH"}
_FX_CODES         = {"XCHG_RATE_INCONSISTENT"}
_DUP_CODES        = {"DUPLICATE_UETR"}

_BIZ_CODES = _COMPLIANCE_CODES | _ACCOUNT_CODES | _ROUTING_CODES | _FX_CODES


def _event_id(msg_id, idx):
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"{msg_id}/{idx}"))


def _parse_base(cre_dt_str):
    try:
        dt = datetime.datetime.fromisoformat(cre_dt_str)
        return dt.astimezone(datetime.timezone.utc)
    except (ValueError, TypeError):
        return datetime.datetime.now(datetime.timezone.utc)


def generate_events(msg_id, uetr, error_entries, tx, rng, *, backdated_hours=0):
    """Return a list of processing event dicts for one pacs.008 message.

    Args:
        msg_id: unique message ID (used for deterministic event IDs)
        uetr: UETR of the payment (may be a duplicate for DUPLICATE_UETR errors)
        error_entries: injected error dicts from the manifest (may be empty)
        tx: transaction dict from the generator (cre_dt, bics, amounts, parties)
        rng: per-message Random instance — does not affect the batch RNG
        backdated_hours: shift base time into the past for stuck-payment scenarios
    """
    base = _parse_base(tx.get("cre_dt", ""))
    if backdated_hours:
        base -= datetime.timedelta(hours=backdated_hours)

    error_codes = {e["code"] for e in error_entries}
    events = []
    offset = 0.0  # running seconds from base

    def ts():
        t = base + datetime.timedelta(seconds=offset)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    def add(event_type, delta, detail):
        nonlocal offset
        offset += max(delta, 0.0)
        status_code, source_system, actor = _SYSTEMS[event_type]
        events.append({
            "event_id":      _event_id(msg_id, len(events)),
            "event_type":    event_type,
            "status_code":   status_code,
            "source_system": source_system,
            "actor":         actor,
            "occurred_at":   ts(),
            "detail":        detail,
        })

    sender  = tx.get("instg_bic", "UNKNOWN")
    receiver = tx.get("instd_bic", "UNKNOWN")
    intrmy  = tx.get("intrmy_bic")
    amount  = tx.get("amt", "0")
    ccy     = tx.get("ccy", "")
    cdtr    = tx.get("cdtr", {})
    cdtr_nm = cdtr.get("nm", "")

    # ── 1. Always: received ────────────────────────────────────────────────────
    add("PAYMENT_RECEIVED", rng.uniform(0.5, 2.0),
        f"pacs.008 received from {sender} → {receiver} | {amount} {ccy} | {msg_id}")

    # ── 2. Always: format validation (XML is XSD-valid by construction) ────────
    add("FORMAT_VALIDATED", rng.uniform(1.5, 5.0),
        "ISO 20022 CBPR+ SR2025 schema check passed; AppHdr BizSvc: swift.cbprplus.03")

    # ── 3. Duplicate check (fast, before network calls) ────────────────────────
    if _DUP_CODES & error_codes:
        err = next(e for e in error_entries if e["code"] == "DUPLICATE_UETR")
        add("DUPLICATE_DETECTED", rng.uniform(2.0, 6.0),
            f"UETR {uetr} already present in transaction registry — {err['detail']}")
        add("EXCEPTION_RAISED", rng.uniform(0.5, 2.0),
            f"Payment queued for exception handling | DUPLICATE_UETR | {msg_id}")
        return events

    # ── 4. Sanctions screening ─────────────────────────────────────────────────
    if _SANCTIONS_CODES & error_codes:
        score = rng.randint(91, 99)
        add("SANCTIONS_HIT", rng.uniform(8.0, 18.0),
            f"Name match: '{cdtr_nm}' — OFAC SDN score 0.{score} (threshold 0.85) | "
            f"list: OFAC-SDN | match type: EXACT_ALIAS")
        add("PAYMENT_HELD", rng.uniform(0.3, 1.0),
            f"Payment placed on compliance hold — analyst review required | {msg_id}")
        add("EXCEPTION_RAISED", rng.uniform(0.5, 2.0),
            f"Routed to Compliance Exception Queue | SANCTIONS_NAME_HIT | {msg_id}")
        return events

    # All other error types pass sanctions (technical / account / routing errors)
    scr_detail = "Name/account screening passed — no matches on OFAC SDN, EU/UKFSF, HMT lists"
    if "BENEFICIARY_NAME_INCOMPLETE" in error_codes:
        scr_detail = (f"Partial name '{cdtr_nm}' screened — score below 0.85 threshold; "
                      "passed with advisory flag")
    add("SANCTIONS_CLEARED", rng.uniform(8.0, 18.0), scr_detail)

    # ── 5. Business / account / routing / FX validation ───────────────────────
    if _BIZ_CODES & error_codes:
        code = next(iter(_BIZ_CODES & error_codes))
        err  = next(e for e in error_entries if e["code"] == code)
        add("BUSINESS_VALIDATION_FAILED", rng.uniform(4.0, 10.0),
            f"{code} | {err['detail']}")
        add("EXCEPTION_RAISED", rng.uniform(0.5, 2.0),
            f"Payment queued for exception handling | {code} | {msg_id}")
        return events

    # ── 6–8. Happy path: routing → settlement ─────────────────────────────────
    route = f"{sender}"
    if intrmy:
        route += f" → {intrmy} (intermediary)"
    route += f" → {receiver}"
    add("ROUTING_RESOLVED", rng.uniform(3.0, 8.0),
        f"Correspondent route resolved: {route}")

    via = f" via {intrmy}" if intrmy else ""
    add("SETTLEMENT_INITIATED", rng.uniform(10.0, 30.0),
        f"Payment instruction forwarded to {receiver}{via} | UETR: {uetr}")

    if backdated_hours:
        # Stuck payment: delayed event, no confirmation
        delay_secs = rng.uniform(3600.0, backdated_hours * 3600.0 - 300.0)
        add("PROCESSING_DELAYED", delay_secs,
            f"No ACCC from {receiver} within SLA window (expected: 2h) — "
            f"payment pending at correspondent{via} | UETR: {uetr}")
        return events

    if intrmy:
        add("CORRESPONDENT_ACK", rng.uniform(30.0, 90.0),
            f"ACK received from intermediary {intrmy} | forwarding to {receiver}")

    add("SETTLEMENT_CONFIRMED", rng.uniform(60.0, 300.0),
        f"ACCC received from {receiver} | settlement complete | "
        f"nostro debit confirmed | UETR: {uetr}")

    return events
