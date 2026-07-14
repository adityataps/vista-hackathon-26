"""Lambda handler: SQS-triggered pacs.008 XML ingest into PostgreSQL.

SQS receives S3 ObjectCreated events for the payments/ prefix.
Downloads each XML from S3, parses key pacs.008 fields, upserts into the
payments table (ON CONFLICT msg_id DO NOTHING for idempotency).
"""
import json
import logging
import os
import re
from decimal import Decimal

import boto3
import defusedxml.ElementTree as ET
import psycopg2

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HEAD_NS = 'urn:iso:std:iso:20022:tech:xsd:head.001.001.02'
PACS_NS = 'urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08'

_db_conn = None


def _get_db():
    global _db_conn
    if _db_conn is None or _db_conn.closed:
        _db_conn = psycopg2.connect(os.environ['DATABASE_URL'])
        _ensure_schema(_db_conn)
    return _db_conn


def _ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id              SERIAL PRIMARY KEY,
                s3_key          TEXT NOT NULL,
                msg_id          TEXT UNIQUE,
                uetr            TEXT,
                instr_id        TEXT,
                e2e_id          TEXT,
                amount          NUMERIC(20, 5),
                currency        VARCHAR(3),
                settlement_date DATE,
                sender_bic      TEXT,
                receiver_bic    TEXT,
                debtor_bic      TEXT,
                creditor_bic    TEXT,
                debtor_name     TEXT,
                debtor_iban     TEXT,
                creditor_name   TEXT,
                creditor_iban   TEXT,
                is_faulty       BOOLEAN DEFAULT FALSE,
                raw_xml         TEXT,
                ingested_at     TIMESTAMP DEFAULT NOW()
            )
        """)
    conn.commit()


def _parse_pacs008(xml_content):
    """Parse a two-fragment pacs.008 file (AppHdr + Document) into a dict."""
    clean = re.sub(r'<\?xml[^?]*\?>', '', xml_content)
    clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL).strip()
    wrapped = (
        f'<root xmlns:head="{HEAD_NS}" xmlns:pacs="{PACS_NS}">'
        + clean
        + '</root>'
    )
    root = ET.fromstring(wrapped)
    h, p = f'{{{HEAD_NS}}}', f'{{{PACS_NS}}}'

    def tx(path):
        el = root.find(path)
        return el.text.strip() if el is not None and el.text else None

    tx_path = f'.//{p}CdtTrfTxInf'
    pmt_id = f'{tx_path}/{p}PmtId'
    dbtr_acct = f'{tx_path}/{p}DbtrAcct/{p}Id'
    cdtr_acct = f'{tx_path}/{p}CdtrAcct/{p}Id'

    amt_el = root.find(f'{tx_path}/{p}IntrBkSttlmAmt')
    amount = Decimal(amt_el.text.strip()) if amt_el is not None and amt_el.text else None
    currency = amt_el.get('Ccy') if amt_el is not None else None

    return {
        'msg_id':         tx(f'.//{h}BizMsgIdr'),
        'uetr':           tx(f'{pmt_id}/{p}UETR'),
        'instr_id':       tx(f'{pmt_id}/{p}InstrId'),
        'e2e_id':         tx(f'{pmt_id}/{p}EndToEndId'),
        'amount':         amount,
        'currency':       currency,
        'settlement_date': tx(f'{tx_path}/{p}IntrBkSttlmDt'),
        'sender_bic':     tx(f'.//{h}Fr/{h}FIId/{h}FinInstnId/{h}BICFI'),
        'receiver_bic':   tx(f'.//{h}To/{h}FIId/{h}FinInstnId/{h}BICFI'),
        'debtor_bic':     tx(f'{tx_path}/{p}DbtrAgt/{p}FinInstnId/{p}BICFI'),
        'creditor_bic':   tx(f'{tx_path}/{p}CdtrAgt/{p}FinInstnId/{p}BICFI'),
        'debtor_name':    tx(f'{tx_path}/{p}Dbtr/{p}Nm'),
        'debtor_iban':    tx(f'{dbtr_acct}/{p}IBAN') or tx(f'{dbtr_acct}/{p}Othr/{p}Id'),
        'creditor_name':  tx(f'{tx_path}/{p}Cdtr/{p}Nm'),
        'creditor_iban':  tx(f'{cdtr_acct}/{p}IBAN') or tx(f'{cdtr_acct}/{p}Othr/{p}Id'),
    }


def _ingest_record(s3_key, parsed, raw_xml):
    is_faulty = 'FAULTY' in s3_key.upper()
    conn = _get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO payments (
                s3_key, msg_id, uetr, instr_id, e2e_id,
                amount, currency, settlement_date,
                sender_bic, receiver_bic, debtor_bic, creditor_bic,
                debtor_name, debtor_iban, creditor_name, creditor_iban,
                is_faulty, raw_xml
            ) VALUES (
                %(s3_key)s, %(msg_id)s, %(uetr)s, %(instr_id)s, %(e2e_id)s,
                %(amount)s, %(currency)s, %(settlement_date)s,
                %(sender_bic)s, %(receiver_bic)s, %(debtor_bic)s, %(creditor_bic)s,
                %(debtor_name)s, %(debtor_iban)s, %(creditor_name)s, %(creditor_iban)s,
                %(is_faulty)s, %(raw_xml)s
            )
            ON CONFLICT (msg_id) DO NOTHING
        """, {**parsed, 's3_key': s3_key, 'is_faulty': is_faulty, 'raw_xml': raw_xml})
    conn.commit()


def lambda_handler(event, context):
    s3 = boto3.client('s3')
    processed = failed = skipped = 0

    for sqs_record in event.get('Records', []):
        try:
            body = json.loads(sqs_record['body'])
        except (json.JSONDecodeError, KeyError):
            logger.warning("unparseable SQS record: %s", sqs_record.get('body', '')[:200])
            skipped += 1
            continue

        for s3_event in body.get('Records', []):
            if not s3_event.get('eventName', '').startswith('ObjectCreated'):
                skipped += 1
                continue
            bucket = s3_event['s3']['bucket']['name']
            key = s3_event['s3']['object']['key']
            if not key.endswith('.xml'):
                logger.info("skipping non-xml key: %s", key)
                skipped += 1
                continue
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                raw_xml = obj['Body'].read().decode('utf-8')
                parsed = _parse_pacs008(raw_xml)
                _ingest_record(key, parsed, raw_xml)
                logger.info("ingested %s (msg_id=%s)", key, parsed.get('msg_id'))
                processed += 1
            except Exception as exc:
                logger.error("failed to ingest %s: %s", key, exc, exc_info=True)
                failed += 1

    return {
        'statusCode': 200,
        'body': json.dumps({'processed': processed, 'failed': failed, 'skipped': skipped}),
    }
