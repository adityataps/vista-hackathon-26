"""Local smoke test of the Lambda handler (no AWS needed).
Run from pacs008-generator/:  python3 aws/local_invoke.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lambda_handler import lambda_handler  # noqa: E402

# 1. direct invocation
r = lambda_handler({"count": 6, "faulty": 2, "seed": 42}, None)
d = json.loads(r["body"])
assert r["statusCode"] == 200
faulty = [m for m in d["messages"] if m["is_faulty"]]
print("Direct:      %d messages, %d faulty, run %s"
      % (len(d["messages"]), len(faulty), d["run_id"]))

# 2. API Gateway style (body as string)
r = lambda_handler({"body": json.dumps({"count": 3, "error_rate": 0.0})}, None)
d = json.loads(r["body"])
assert r["statusCode"] == 200 and len(d["messages"]) == 3
print("API GW body: 3 messages, 0 faulty ok")

# 3. error case
r = lambda_handler({"count": 5, "faulty": 99}, None)
assert r["statusCode"] == 400
print("Validation:  400 for faulty > count ok")

print("Smoke test OK")
