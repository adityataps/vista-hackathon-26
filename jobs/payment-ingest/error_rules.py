"""Business-rule error detection for pacs.008 payments, ported from
error-list/agent_error_knowledge.yaml (see jobs/pacs008-generator).

Pure functions operating on the dict produced by handler._parse_pacs008() -
no AWS/DB dependency, so this is easy to unit test in isolation.
"""
import difflib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional, Set

# ISO 13616 IBAN length by country code (extend as needed).
IBAN_LENGTH_BY_COUNTRY = {
    "AD": 24, "AT": 20, "BE": 16, "CH": 21, "CY": 28, "CZ": 24, "DE": 22,
    "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27,
    "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LU": 20, "LV": 21,
    "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "SE": 24,
    "SI": 19, "SK": 24, "SM": 27,
}

INCOMPLETE_NAME_RE = re.compile(r"^[A-Z]\.$")
PLACEHOLDER_NAMES = {"UNKNOWN", "N/A", "NA", "TBD"}
SANCTIONS_MATCH_THRESHOLD = 0.85
XCHG_RATE_TOLERANCE = 0.01  # 1%


@dataclass(frozen=True)
class ErrorHit:
    code: str
    message: str


def _iban_mod97_valid(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    if len(iban) < 4:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        expanded = "".join(str(int(c, 36)) if c.isalpha() else c for c in rearranged)
        return int(expanded) % 97 == 1
    except (ValueError, TypeError):
        return False


def check_iban_checksum(payment: dict) -> Optional[ErrorHit]:
    iban = payment.get("creditor_iban") or payment.get("debtor_iban")
    if not iban or not re.match(r"^[A-Za-z]{2}\d", iban):
        return None  # not IBAN-shaped (e.g. an Othr/Id account number) - skip
    if not _iban_mod97_valid(iban):
        return ErrorHit(
            "IBAN_INVALID_CHECKSUM",
            f"IBAN '{iban}' fails ISO 7064 mod-97 checksum validation.",
        )
    return None


def check_iban_length(payment: dict) -> List[ErrorHit]:
    hits = []
    for field_name in ("debtor_iban", "creditor_iban"):
        iban = payment.get(field_name)
        if not iban or not re.match(r"^[A-Za-z]{2}\d", iban):
            continue
        country = iban[:2].upper()
        expected = IBAN_LENGTH_BY_COUNTRY.get(country)
        if expected and len(iban) != expected:
            hits.append(ErrorHit(
                "IBAN_WRONG_LENGTH",
                f"{field_name} '{iban}' has length {len(iban)}, expected {expected} for country {country}.",
            ))
    return hits


def check_bic_iban_country_mismatch(payment: dict) -> List[ErrorHit]:
    hits = []
    pairs = [
        ("debtor_bic", "debtor_iban"),
        ("creditor_bic", "creditor_iban"),
    ]
    for bic_field, iban_field in pairs:
        bic = payment.get(bic_field)
        iban = payment.get(iban_field)
        if not bic or not iban or len(bic) < 6 or not re.match(r"^[A-Za-z]{2}\d", iban):
            continue
        bic_country = bic[4:6].upper()
        iban_country = iban[:2].upper()
        if bic_country != iban_country:
            hits.append(ErrorHit(
                "BIC_IBAN_COUNTRY_MISMATCH",
                f"{bic_field} '{bic}' country ({bic_country}) does not match "
                f"{iban_field} '{iban}' country ({iban_country}).",
            ))
    return hits


def check_bic_unknown(payment: dict, known_bics: Optional[Set[str]]) -> List[ErrorHit]:
    if not known_bics:
        return []
    hits = []
    for field_name in ("sender_bic", "receiver_bic", "debtor_bic", "creditor_bic"):
        bic = payment.get(field_name)
        if bic and bic not in known_bics:
            hits.append(ErrorHit(
                "BIC_UNKNOWN",
                f"{field_name} '{bic}' is not present in the active BIC directory.",
            ))
    return hits


def _is_incomplete_name(name: str) -> bool:
    name = name.strip()
    if len(name) < 5:
        return True
    if INCOMPLETE_NAME_RE.match(name):
        return True
    if name.upper() in PLACEHOLDER_NAMES:
        return True
    if len(name.split()) == 1 and len(name) < 8:
        return True
    return False


def check_beneficiary_name_incomplete(payment: dict) -> Optional[ErrorHit]:
    name = payment.get("creditor_name")
    if name and _is_incomplete_name(name):
        return ErrorHit(
            "BENEFICIARY_NAME_INCOMPLETE",
            f"Cdtr/Nm '{name}' looks incomplete (too short / initials only / placeholder).",
        )
    return None


def check_address_incomplete(payment: dict) -> Optional[ErrorHit]:
    ctry = payment.get("creditor_ctry")
    has_country_only = bool(ctry) and not any(
        payment.get(f) for f in ("creditor_twn_nm", "creditor_strt_nm")
    )
    if has_country_only:
        return ErrorHit(
            "ADDRESS_INCOMPLETE",
            "Cdtr/PstlAdr only has Ctry populated; missing TwnNm/StrtNm/AdrLine.",
        )
    return None


def check_duplicate_uetr(payment: dict, existing_uetrs: Optional[Iterable[str]]) -> Optional[ErrorHit]:
    if not existing_uetrs:
        return None
    uetr = payment.get("uetr")
    if uetr and uetr in set(existing_uetrs):
        return ErrorHit(
            "DUPLICATE_UETR",
            f"UETR '{uetr}' already exists in the payments table (possible duplicate submission).",
        )
    return None


def _to_decimal(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def check_xchg_rate_inconsistent(payment: dict) -> Optional[ErrorHit]:
    instd_amt = _to_decimal(payment.get("instd_amt"))
    xchg_rate = _to_decimal(payment.get("xchg_rate"))
    sttlm_amt = _to_decimal(payment.get("amount"))
    instd_ccy = payment.get("instd_amt_ccy")
    sttlm_ccy = payment.get("currency")

    if instd_amt is None or xchg_rate is None or sttlm_amt is None:
        return None
    if instd_ccy and sttlm_ccy and instd_ccy == sttlm_ccy:
        return None
    if sttlm_amt == 0:
        return None

    expected = instd_amt * xchg_rate
    deviation = abs(expected - sttlm_amt) / sttlm_amt
    if deviation > XCHG_RATE_TOLERANCE:
        return ErrorHit(
            "XCHG_RATE_INCONSISTENT",
            f"InstdAmt({instd_amt}) * XchgRate({xchg_rate}) = {expected}, "
            f"deviates {deviation:.2%} from IntrBkSttlmAmt({sttlm_amt}) - exceeds 1% tolerance.",
        )
    return None


def _name_matches_watchlist(name: str, watchlist: Iterable[str]) -> Optional[str]:
    name_norm = name.strip().lower()
    for entry in watchlist:
        score = difflib.SequenceMatcher(None, name_norm, entry.strip().lower()).ratio()
        if score >= SANCTIONS_MATCH_THRESHOLD:
            return entry
    return None


def check_sanctions_name_hit(payment: dict, watchlist: Optional[Iterable[str]]) -> List[ErrorHit]:
    if not watchlist:
        return []
    hits = []
    for field_name in ("creditor_name", "debtor_name"):
        name = payment.get(field_name)
        if not name:
            continue
        match = _name_matches_watchlist(name, watchlist)
        if match:
            hits.append(ErrorHit(
                "SANCTIONS_NAME_HIT",
                f"{field_name} '{name}' fuzzy-matches watchlist entry '{match}'.",
            ))
    return hits


def check_account_closed(payment: dict, closed_accounts: Optional[Iterable[str]]) -> Optional[ErrorHit]:
    if not closed_accounts:
        return None
    closed = set(closed_accounts)
    cdtr_account = payment.get("creditor_iban")
    if cdtr_account and cdtr_account in closed:
        return ErrorHit(
            "ACCOUNT_CLOSED",
            f"Beneficiary account '{cdtr_account}' is marked closed in the account-status reference data.",
        )
    return None


def detect_errors(
    payment: dict,
    known_bics: Optional[Set[str]] = None,
    watchlist: Optional[Iterable[str]] = None,
    closed_accounts: Optional[Iterable[str]] = None,
    existing_uetrs: Optional[Iterable[str]] = None,
) -> List[ErrorHit]:
    """Run every rule against a parsed payment dict and return all hits found.

    Reference-data-backed rules (known_bics/watchlist/closed_accounts/
    existing_uetrs) are skipped gracefully when the corresponding data isn't
    supplied.
    """
    hits: List[ErrorHit] = []

    single_hit_checks = (
        check_iban_checksum,
        check_beneficiary_name_incomplete,
        check_address_incomplete,
        check_xchg_rate_inconsistent,
    )
    for check in single_hit_checks:
        result = check(payment)
        if result:
            hits.append(result)

    hits.extend(check_iban_length(payment))
    hits.extend(check_bic_iban_country_mismatch(payment))
    hits.extend(check_bic_unknown(payment, known_bics))
    hits.extend(check_sanctions_name_hit(payment, watchlist))

    dup = check_duplicate_uetr(payment, existing_uetrs)
    if dup:
        hits.append(dup)

    closed = check_account_closed(payment, closed_accounts)
    if closed:
        hits.append(closed)

    return hits


def format_error_msg(hits: List[ErrorHit]) -> Optional[str]:
    if not hits:
        return None
    return "; ".join(f"{hit.code}: {hit.message}" for hit in hits)
