import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pacs008_generator.generator import generate_batch


def _batch(**kw):
    kw.setdefault("count", 30)
    kw.setdefault("error_rate", 0.4)
    kw.setdefault("seed", 99)
    kw.setdefault("write_files", False)
    return generate_batch(**kw)


def test_uetr_unique_except_injected_duplicates():
    m = _batch()
    dup_files = {x["file"] for x in m["messages"]
                 if any(e["code"] == "DUPLICATE_UETR" for e in x["errors"])}
    uetrs = [x["uetr"] for x in m["messages"] if x["file"] not in dup_files]
    assert len(uetrs) == len(set(uetrs))


def test_msgid_instrid_e2e_unique():
    m = _batch()
    for field in ("msg_id",):
        vals = [x[field] for x in m["messages"]]
        assert len(vals) == len(set(vals))
    instr = [x["xml"].split("<pacs:InstrId>")[1].split("<")[0] for x in m["messages"]]
    e2e = [x["xml"].split("<pacs:EndToEndId>")[1].split("<")[0] for x in m["messages"]]
    assert len(instr) == len(set(instr))
    assert len(e2e) == len(set(e2e))


def test_no_business_duplicates():
    m = _batch(count=40, error_rate=0.0)
    keys = set()
    for x in m["messages"]:
        xml = x["xml"]
        amt = xml.split("<pacs:IntrBkSttlmAmt")[1].split(">")[1].split("<")[0]
        ccy = xml.split('IntrBkSttlmAmt Ccy="')[1][:3]
        cdtr_acct = xml.split("<pacs:CdtrAcct>")[1].split("</pacs:CdtrAcct>")[0]
        dbtr_acct = xml.split("<pacs:DbtrAcct>")[1].split("</pacs:DbtrAcct>")[0]
        key = (dbtr_acct, cdtr_acct, amt, ccy)
        assert key not in keys, "business duplicate: %s" % (key,)
        keys.add(key)


def test_runs_without_seed_have_distinct_msg_ids():
    a = generate_batch(count=3, error_rate=0, seed=None, write_files=False)
    b = generate_batch(count=3, error_rate=0, seed=None, write_files=False)
    ids_a = {x["msg_id"] for x in a["messages"]}
    ids_b = {x["msg_id"] for x in b["messages"]}
    assert not (ids_a & ids_b)


def test_absolute_faulty_count():
    m = _batch(count=20, faulty=7)
    assert sum(1 for x in m["messages"] if x["is_faulty"]) <= 7
    m2 = _batch(count=20, faulty=7, error_codes=["IBAN_INVALID_CHECKSUM"])
    assert sum(1 for x in m2["messages"] if x["is_faulty"]) == 7


def test_faulty_out_of_range():
    with pytest.raises(ValueError):
        _batch(count=5, faulty=9)
