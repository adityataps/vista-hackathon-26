import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pacs008_generator import errors, validator
from pacs008_generator.generator import generate_batch

SEED = 42


def _batch(**kw):
    kw.setdefault("count", 12)
    kw.setdefault("error_rate", 0.5)
    kw.setdefault("seed", SEED)
    kw.setdefault("write_files", False)
    return generate_batch(**kw)


def test_all_messages_schema_valid():
    m = _batch()
    for msg in m["messages"]:
        assert validator.validate(msg["xml"]) == [], msg["file"]


def test_error_rate_and_manifest_consistency():
    m = _batch()
    faulty = [x for x in m["messages"] if x["is_faulty"]]
    assert len(faulty) == 6  # 12 * 0.5
    for x in m["messages"]:
        assert bool(x["errors"]) == x["is_faulty"]


def test_seed_reproducible():
    a, b = _batch(), _batch()
    assert [x["xml"] for x in a["messages"]] == [x["xml"] for x in b["messages"]]
    assert json.dumps(a["messages"][0]["errors"]) == json.dumps(b["messages"][0]["errors"])


def test_error_codes_filter():
    m = _batch(error_codes=["IBAN_INVALID_CHECKSUM"], count=10, error_rate=0.4)
    for x in m["messages"]:
        for e in x["errors"]:
            assert e["code"] == "IBAN_INVALID_CHECKSUM"


def test_every_injector_stays_schema_valid():
    codes = [e["code"] for e in errors.load_catalog()]
    for code in codes:
        m = _batch(count=6, error_rate=1.0, error_codes=[code], seed=7)
        for msg in m["messages"]:
            assert validator.validate(msg["xml"]) == [], (code, msg["file"])
        # at least one message must actually carry the error
        assert any(x["errors"] and x["errors"][0]["code"] == code
                   for x in m["messages"]), code


def test_faulty_messages_differ_from_clean():
    """Injected business errors must be detectable (IBAN checksum example)."""
    m = _batch(count=8, error_rate=1.0, error_codes=["IBAN_INVALID_CHECKSUM"], seed=1)
    for x in m["messages"]:
        detail = x["errors"][0]["detail"]
        bad_iban = detail.split()[2]
        s = bad_iban[4:] + bad_iban[:4]
        assert int("".join(str(int(c, 36)) for c in s)) % 97 != 1


def test_writes_files_and_manifest(tmp_path):
    out = str(tmp_path / "out")
    m = generate_batch(count=5, error_rate=0.4, seed=3, out_dir=out)
    files = os.listdir(out)
    assert "manifest.json" in files
    assert len([f for f in files if f.endswith(".xml")]) == 5
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
        slim = json.load(f)
    assert len(slim["messages"]) == 5
    assert all("xml" not in x for x in slim["messages"])


def test_invalid_error_code_raises():
    with pytest.raises(ValueError):
        _batch(error_codes=["DOES_NOT_EXIST"])
