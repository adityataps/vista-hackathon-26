import json
from difflib import SequenceMatcher

from langchain_core.tools import tool

# Simplified OFAC SDN entries sufficient for demo scenarios
SDN_LIST = [
    {
        "name": "NOVAYA ZVEZDA SHIPPING LLC",
        "aliases": ["Novaya Star", "NZ Shipping", "Novaya Star Shipping", "Novaya Zvezda"],
        "country": "RU",
        "program": "RUSSIA-EO14024",
        "list": "OFAC SDN",
        "notes": "Re-registered in UAE 2024; vessel ownership links to listed entities",
    },
    {
        "name": "IRAN SHIPPING LINES",
        "aliases": ["IRISL", "Islamic Republic of Iran Shipping"],
        "country": "IR",
        "program": "IRAN",
        "list": "OFAC SDN",
        "notes": "State-owned shipping company",
    },
    {
        "name": "KOREA MINING DEVELOPMENT TRADING CORPORATION",
        "aliases": ["KOMID", "Korea Mining Development"],
        "country": "KP",
        "program": "NPWMD",
        "list": "OFAC SDN",
        "notes": "DPRK arms trafficking entity",
    },
    {
        "name": "AL-RASHID TRUST",
        "aliases": ["Al Rashid Trust", "Alrashid Trust"],
        "country": "PK",
        "program": "SDGT",
        "list": "OFAC SDN",
        "notes": "Terror finance network",
    },
]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


@tool
def screen_entity_tool(name: str) -> str:
    """Screen an entity name against the sanctions list using fuzzy matching.
    Returns match result with score and matched SDN entry if above threshold."""
    best_score = 0.0
    best_entry = None
    best_alias = None

    for entry in SDN_LIST:
        candidates = [entry["name"]] + entry.get("aliases", [])
        for candidate in candidates:
            score = _similarity(name, candidate)
            if score > best_score:
                best_score = score
                best_entry = entry
                best_alias = candidate

    if best_score >= 0.70:
        return json.dumps({
            "match": True,
            "score": round(best_score, 3),
            "matched_alias": best_alias,
            "entry": best_entry,
            "threshold": 0.70,
        })
    return json.dumps({
        "match": False,
        "score": round(best_score, 3),
        "closest_alias": best_alias,
        "threshold": 0.70,
    })


@tool
def check_address_completeness_tool(address_json: str) -> str:
    """Check if a creditor postal address meets FATF Travel Rule requirements.
    address_json should be a JSON object with keys like Ctry, TwnNm, StrtNm, AdrLine.
    Returns {complete, missing_fields, fatf_compliant}."""
    try:
        address = json.loads(address_json)
    except Exception:
        return json.dumps({"complete": False, "error": "address_json must be valid JSON"})

    required = ["Ctry"]
    recommended = ["TwnNm", "StrtNm"]
    missing_required = [f for f in required if not address.get(f)]
    missing_recommended = [f for f in recommended if not address.get(f)]
    has_adr_line = bool(address.get("AdrLine"))

    fatf_compliant = not missing_required and (not missing_recommended or has_adr_line)

    return json.dumps({
        "complete": fatf_compliant,
        "missing_required_fields": missing_required,
        "missing_recommended_fields": missing_recommended,
        "has_adr_line_fallback": has_adr_line,
        "fatf_compliant": fatf_compliant,
        "note": "CBPR+ SR2026 requires country + town + street or AdrLine",
    })
