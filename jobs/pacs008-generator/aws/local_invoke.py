"""Lokaler Smoke-Test des Lambda-Handlers (ohne AWS).
Aufruf aus pacs008-generator/:  python3 aws/local_invoke.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lambda_handler import lambda_handler  # noqa: E402

# 1. direkte Invocation
r = lambda_handler({"count": 6, "faulty": 2, "seed": 42}, None)
d = json.loads(r["body"])
assert r["statusCode"] == 200
faulty = [m for m in d["messages"] if m["is_faulty"]]
print("Direkt:      %d Meldungen, %d fehlerhaft, run %s"
      % (len(d["messages"]), len(faulty), d["run_id"]))

# 2. API-Gateway-Stil (body als String)
r = lambda_handler({"body": json.dumps({"count": 3, "error_rate": 0.0})}, None)
d = json.loads(r["body"])
assert r["statusCode"] == 200 and len(d["messages"]) == 3
print("API-GW-Body: 3 Meldungen, 0 fehlerhaft ok")

# 3. Fehlerfall
r = lambda_handler({"count": 5, "faulty": 99}, None)
assert r["statusCode"] == 400
print("Validierung: 400 bei faulty > count ok")

print("Smoke-Test OK")
