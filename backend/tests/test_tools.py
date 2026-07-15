import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.tools.technical_tools import validate_iban_tool, validate_bic_tool, check_fx_tool


def test_validate_iban_tool_invalid_checksum():
    # GB29NWBK60161331926820 has a bad checksum (last digit changed) — should fail
    result = json.loads(validate_iban_tool.invoke({"iban": "GB29NWBK60161331926820"}))
    assert result["valid"] is False
    assert any(e["code"] == "IBAN_INVALID_CHECKSUM" for e in result["errors"])


def test_validate_iban_tool_invalid_format():
    result = json.loads(validate_iban_tool.invoke({"iban": "NOT_AN_IBAN"}))
    assert result["valid"] is False


def test_validate_bic_tool_valid():
    result = json.loads(validate_bic_tool.invoke({"bic": "DEUTDEDB"}))
    assert result["valid"] is True
    assert result["country"] == "DE"


def test_validate_bic_tool_invalid_country():
    result = json.loads(validate_bic_tool.invoke({"bic": "DEUTXXDB"}))
    assert result["valid"] is False
    assert "XX" in result["error"]


def test_check_fx_tool_consistent():
    result = json.loads(check_fx_tool.invoke({"instd_amt": 1000.0, "sttlm_amt": 850.0, "rate": 0.85}))
    assert result["consistent"] is True


def test_check_fx_tool_inconsistent():
    result = json.loads(check_fx_tool.invoke({"instd_amt": 1000.0, "sttlm_amt": 850.0, "rate": 0.75}))
    assert result["consistent"] is False
    assert result["deviation_pct"] > 1.0
