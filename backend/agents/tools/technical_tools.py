import json
import os
import sys

from langchain_core.tools import tool

# Resolve paths relative to this file's absolute location
_tools_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(os.path.dirname(_tools_dir))         # backend/
_project_root = os.path.dirname(_backend_dir)                       # project root

# Add backend/ so `db` is importable; add jobs/pacs008-generator/ for iban_validator
sys.path.insert(0, _backend_dir)
sys.path.insert(0, os.path.join(_project_root, "jobs", "pacs008-generator"))

from pacs008_generator.iban_validator import validate_iban
from db import get_db

ISO3166 = {
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS",
    "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
    "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE",
    "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF",
    "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT", "JE", "JM",
    "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC",
    "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
    "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA",
    "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG",
    "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS",
    "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO",
    "TR", "TT", "TV", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI", "VN",
    "VU", "WF", "WS", "XK", "YE", "YT", "ZA", "ZM", "ZW",
}


@tool
def validate_iban_tool(iban: str) -> str:
    """Validate an IBAN using ISO 7064 mod-97 check. Returns validation result with errors."""
    result = validate_iban(iban)
    return json.dumps(result)


@tool
def validate_bic_tool(bic: str) -> str:
    """Validate a BIC/SWIFT code format and country code (positions 5-6)."""
    bic = bic.strip().upper()
    if len(bic) not in (8, 11):
        return json.dumps({
            "bic": bic,
            "valid": False,
            "error": f"BIC must be 8 or 11 chars, got {len(bic)}",
        })
    country = bic[4:6]
    if country not in ISO3166:
        return json.dumps({
            "bic": bic,
            "valid": False,
            "error": f"Country code '{country}' (positions 5-6) is not a valid ISO 3166-1 alpha-2 code",
        })
    return json.dumps({
        "bic": bic,
        "valid": True,
        "country": country,
        "institution": bic[:4],
        "location": bic[6:8],
    })


@tool
def check_duplicate_tool(uetr: str, msg_id: str) -> str:
    """Check if a payment with the same UETR already exists (excluding the current msg_id)."""
    conn = get_db()
    if not conn:
        return json.dumps({"duplicate": False, "error": "DB unavailable"})
    with conn.cursor() as cur:
        cur.execute("""
            SELECT msg_id, amount, currency, sender_bic, receiver_bic, ingested_at
            FROM payments
            WHERE uetr = %s AND msg_id != %s
        """, (uetr, msg_id))
        rows = cur.fetchall()
    if not rows:
        return json.dumps({"duplicate": False, "uetr": uetr})
    cols = ["msg_id", "amount", "currency", "sender_bic", "receiver_bic", "ingested_at"]
    duplicates = [
        dict(zip(cols, [str(v) if v is not None else None for v in r]))
        for r in rows
    ]
    return json.dumps({"duplicate": True, "uetr": uetr, "original_payments": duplicates})


@tool
def check_fx_tool(instd_amt: float, sttlm_amt: float, rate: float) -> str:
    """Check if instd_amt * rate is consistent with sttlm_amt. Flags >1% deviation."""
    if rate <= 0 or sttlm_amt <= 0:
        return json.dumps({"consistent": False, "error": "rate and sttlm_amt must be positive"})
    expected = instd_amt * rate
    deviation = abs(expected - sttlm_amt) / sttlm_amt
    consistent = deviation <= 0.01
    return json.dumps({
        "consistent": consistent,
        "instd_amt": instd_amt,
        "sttlm_amt": sttlm_amt,
        "rate": rate,
        "expected_sttlm_amt": round(expected, 5),
        "deviation_pct": round(deviation * 100, 3),
    })
