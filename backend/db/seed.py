"""
Seed script for the PayInvestigator mock DB (SQLite).

Creates MINF (latest payment state) and NEWJOURNAL (history) tables from
schema.sql and populates them with ~30 mock payments, including the three
demo scenarios:
  1. Bad IBAN checksum      -> MID000001
  2. Sanctions screening hit -> MID000002
  3. Duplicate payment       -> MID000003 / MID000004

Run:
    python seed.py
Produces:
    payinvestigator.db (SQLite file, alongside this script)
"""
import sqlite3
import random
from datetime import datetime, timedelta, UTC
from pathlib import Path

DB_PATH = Path(__file__).parent / "payinvestigator.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

CURRENCIES = ["USD", "EUR", "GBP", "CHF", "JPY"]
COUNTRIES = ["US", "GB", "DE", "FR", "CH", "IR", "RU"]
BICS = [
    ("CITIUS33XXX", "Citibank N.A.", "US"),
    ("DEUTDEFFXXX", "Deutsche Bank AG", "DE"),
    ("BARCGB22XXX", "Barclays Bank", "GB"),
    ("UBSWCHZH80A", "UBS Switzerland AG", "CH"),
    ("BNPAFRPPXXX", "BNP Paribas", "FR"),
]


def now_iso(offset_minutes=0):
    return (datetime.now(UTC) + timedelta(minutes=offset_minutes)).strftime("%Y-%m-%dT%H:%M:%S")


def build_schema(conn):
    conn.executescript(SCHEMA_PATH.read_text())


def insert_minf(conn, row):
    cols = ",".join(row.keys())
    placeholders = ",".join("?" for _ in row)
    conn.execute(f"INSERT INTO MINF ({cols}) VALUES ({placeholders})", list(row.values()))


def insert_journal(conn, row):
    cols = ",".join(row.keys())
    placeholders = ",".join("?" for _ in row)
    conn.execute(f"INSERT INTO NEWJOURNAL ({cols}) VALUES ({placeholders})", list(row.values()))


def base_payment(mid, status, amount, currency, dbtr, cdtr, dbt_iban, cdt_iban,
                  dbtr_bic, cdtr_bic, country, created_offset, error_code=None,
                  error_desc=None, duplicate_index=0, sanctions_flag="N",
                  sanctions_score=None, last_action="CREATED"):
    created = now_iso(created_offset)
    return dict(
        P_MID=mid,
        P_OFFICE="001",
        P_MSG_TYPE="pacs.008",
        P_STATUS=status,
        P_LAST_ACTION=last_action,
        P_ERROR_CODE=error_code,
        P_ERROR_DESC=error_desc,
        P_AMOUNT=amount,
        P_CURRENCY=currency,
        P_VALUE_DATE=datetime.now(UTC).strftime("%Y-%m-%d"),
        P_PRIORITY="NORM",
        P_DBTR_NAME=dbtr,
        P_DBT_ACCT_NB=dbt_iban,
        P_DBT_ACCT_CCY=currency,
        P_DBTR_AGT_BIC=dbtr_bic,
        P_CDTR_NAME=cdtr,
        P_CDT_ACCT_NB=cdt_iban,
        P_CDT_ACCT_CCY=currency,
        P_CDTR_AGT_BIC=cdtr_bic,
        P_COUNTRY_CODE=country,
        P_DUPLICATE_INDEX=duplicate_index,
        P_SANCTIONS_HIT_FLAG=sanctions_flag,
        P_SANCTIONS_SCORE=sanctions_score,
        XML_MSG=f"<FIToFICstmrCdtTrf><MsgId>{mid}</MsgId><Amt>{amount}</Amt><Ccy>{currency}</Ccy></FIToFICstmrCdtTrf>",
        P_CREATE_DATETIME=created,
        P_LAST_UPDATE_DATETIME=created,
    )


def seed(conn):
    rng = random.Random(42)

    # ---------------------------------------------------------------
    # Scenario 1: Bad IBAN checksum -> Technical Diagnosis Agent fixes it
    # ---------------------------------------------------------------
    mid = "MID000001"
    p = base_payment(
        mid, status="PENDING_REPAIR", amount=15250.00, currency="EUR",
        dbtr="Acme Manufacturing Ltd", cdtr="Global Parts GmbH",
        dbt_iban="GB29NWBK60161331926819", cdt_iban="DE89370400440532013001",  # bad checksum on purpose
        dbtr_bic="BARCGB22XXX", cdtr_bic="DEUTDEFFXXX", country="DE",
        created_offset=-15, error_code="AC04", error_desc="Invalid IBAN checksum on beneficiary account",
        last_action="VALIDATION_FAILED",
    )
    insert_minf(conn, p)
    insert_journal(conn, dict(
        MID=mid, OFFICE="001", TIME_STAMP=now_iso(-15), STATUS="NEW",
        ACTIONID1="CREATE", ACTIONID2=None, USERNAME="SYSTEM", MODULE_ID="INTAKE_AGENT",
        ERROR_CODE=None, ERROR_DESC=None, ERROR_PARAMS=None, ERROR_SEVERITY=1,
        FIELD_LOGICAL_ID=None, FLOW_ID="FLOW-1001", FAULT="N",
    ))
    insert_journal(conn, dict(
        MID=mid, OFFICE="001", TIME_STAMP=now_iso(-14), STATUS="PENDING_REPAIR",
        ACTIONID1="VALIDATION_FAILED", ACTIONID2="AC04", USERNAME="SYSTEM",
        MODULE_ID="INVESTIGATION_AGENT", ERROR_CODE="AC04",
        ERROR_DESC="Invalid IBAN checksum on beneficiary account",
        ERROR_PARAMS='{"field":"CDT_ACCT_NB","value":"DE89370400440532013001"}',
        ERROR_SEVERITY=3, FIELD_LOGICAL_ID="CDT_ACCT_NB", FLOW_ID="FLOW-1001", FAULT="Y",
    ))

    # ---------------------------------------------------------------
    # Scenario 2: Sanctions screening hit -> Compliance Agent recommends hold
    # ---------------------------------------------------------------
    mid = "MID000002"
    p = base_payment(
        mid, status="HELD_COMPLIANCE", amount=98000.00, currency="USD",
        dbtr="Northwind Trading Co", cdtr="Vostok Import Export",
        dbt_iban="US64SVBKUS6S3300958879", cdt_iban="RU027700111122223333",
        dbtr_bic="CITIUS33XXX", cdtr_bic="BARCGB22XXX", country="RU",
        created_offset=-45, error_code="SANC01", error_desc="Beneficiary name partial match on sanctions list",
        sanctions_flag="Y", sanctions_score=87.5, last_action="SANCTIONS_HOLD",
    )
    insert_minf(conn, p)
    insert_journal(conn, dict(
        MID=mid, OFFICE="001", TIME_STAMP=now_iso(-45), STATUS="NEW",
        ACTIONID1="CREATE", ACTIONID2=None, USERNAME="SYSTEM", MODULE_ID="INTAKE_AGENT",
        ERROR_CODE=None, ERROR_DESC=None, ERROR_PARAMS=None, ERROR_SEVERITY=1,
        FIELD_LOGICAL_ID=None, FLOW_ID="FLOW-1002", FAULT="N",
    ))
    insert_journal(conn, dict(
        MID=mid, OFFICE="001", TIME_STAMP=now_iso(-44), STATUS="HELD_COMPLIANCE",
        ACTIONID1="SANCTIONS_HOLD", ACTIONID2="SANC01", USERNAME="COMPLIANCE_AGENT",
        MODULE_ID="COMPLIANCE_AGENT", ERROR_CODE="SANC01",
        ERROR_DESC="Beneficiary name partial match (87.5%) on OFAC SDN list entry 'Vostok Import-Export'",
        ERROR_PARAMS='{"matched_entity":"Vostok Import-Export","score":87.5}',
        ERROR_SEVERITY=4, FIELD_LOGICAL_ID="CDTR_NAME", FLOW_ID="FLOW-1002", FAULT="Y",
    ))

    # ---------------------------------------------------------------
    # Scenario 3: Duplicate payment -> second submission flagged/cancelled
    # ---------------------------------------------------------------
    mid_a = "MID000003"
    mid_b = "MID000004"
    common = dict(
        amount=5000.00, currency="GBP", dbtr="Sunrise Retail Ltd", cdtr="Harbor Logistics Inc",
        dbt_iban="GB33BUKB20201555555555", cdt_iban="GB94BARC20201530093459",
        dbtr_bic="BARCGB22XXX", cdtr_bic="BARCGB22XXX", country="GB",
    )
    p1 = base_payment(mid_a, status="COMPLETED", created_offset=-120, last_action="SETTLED", **common)
    p2 = base_payment(
        mid_b, status="HELD_DUPLICATE", created_offset=-2, error_code="DUPE01",
        error_desc="Duplicate of MID000003 (same amount/parties within 2 min)",
        duplicate_index=1, last_action="DUPLICATE_HOLD", **common,
    )
    insert_minf(conn, p1)
    insert_minf(conn, p2)
    insert_journal(conn, dict(
        MID=mid_a, OFFICE="001", TIME_STAMP=now_iso(-120), STATUS="COMPLETED",
        ACTIONID1="SETTLE", ACTIONID2=None, USERNAME="SYSTEM", MODULE_ID="RESOLUTION_AGENT",
        ERROR_CODE=None, ERROR_DESC=None, ERROR_PARAMS=None, ERROR_SEVERITY=1,
        FIELD_LOGICAL_ID=None, FLOW_ID="FLOW-1003", FAULT="N",
    ))
    insert_journal(conn, dict(
        MID=mid_b, OFFICE="001", TIME_STAMP=now_iso(-2), STATUS="HELD_DUPLICATE",
        ACTIONID1="DUPLICATE_HOLD", ACTIONID2="DUPE01", USERNAME="TECHNICAL_DIAGNOSIS_AGENT",
        MODULE_ID="TECHNICAL_DIAGNOSIS_AGENT", ERROR_CODE="DUPE01",
        ERROR_DESC="Duplicate of MID000003 (same amount/parties within 2 min)",
        ERROR_PARAMS='{"original_mid":"MID000003"}', ERROR_SEVERITY=3,
        FIELD_LOGICAL_ID=None, FLOW_ID="FLOW-1004", FAULT="Y",
    ))

    # ---------------------------------------------------------------
    # Filler payments (~26 more) in various statuses, no incidents
    # ---------------------------------------------------------------
    statuses = ["COMPLETED", "COMPLETED", "COMPLETED", "PENDING_APPROVAL", "RELEASED", "REJECTED"]
    for i in range(5, 31):
        mid = f"MID{i:06d}"
        bic_d = rng.choice(BICS)
        bic_c = rng.choice(BICS)
        status = rng.choice(statuses)
        p = base_payment(
            mid, status=status, amount=round(rng.uniform(100, 50000), 2),
            currency=rng.choice(CURRENCIES),
            dbtr=f"Company {i} Ltd", cdtr=f"Vendor {i} Inc",
            dbt_iban=f"GB{10+i:02d}NWBK6016133192{i:04d}",
            cdt_iban=f"DE{10+i:02d}370400440532{i:06d}",
            dbtr_bic=bic_d[0], cdtr_bic=bic_c[0],
            country=rng.choice(COUNTRIES),
            created_offset=-rng.randint(5, 500),
            last_action="SETTLED" if status == "COMPLETED" else status,
        )
        insert_minf(conn, p)
        insert_journal(conn, dict(
            MID=mid, OFFICE="001", TIME_STAMP=p["P_CREATE_DATETIME"], STATUS="NEW",
            ACTIONID1="CREATE", ACTIONID2=None, USERNAME="SYSTEM", MODULE_ID="INTAKE_AGENT",
            ERROR_CODE=None, ERROR_DESC=None, ERROR_PARAMS=None, ERROR_SEVERITY=1,
            FIELD_LOGICAL_ID=None, FLOW_ID=f"FLOW-{1000+i}", FAULT="N",
        ))
        insert_journal(conn, dict(
            MID=mid, OFFICE="001", TIME_STAMP=p["P_LAST_UPDATE_DATETIME"], STATUS=status,
            ACTIONID1=p["P_LAST_ACTION"], ACTIONID2=None, USERNAME="SYSTEM",
            MODULE_ID="RESOLUTION_AGENT", ERROR_CODE=None, ERROR_DESC=None,
            ERROR_PARAMS=None, ERROR_SEVERITY=1, FIELD_LOGICAL_ID=None,
            FLOW_ID=f"FLOW-{1000+i}", FAULT="N",
        ))


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        build_schema(conn)
        seed(conn)
        conn.commit()
        n_minf = conn.execute("SELECT COUNT(*) FROM MINF").fetchone()[0]
        n_journal = conn.execute("SELECT COUNT(*) FROM NEWJOURNAL").fetchone()[0]
        print(f"Created {DB_PATH} with {n_minf} MINF rows and {n_journal} NEWJOURNAL rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
