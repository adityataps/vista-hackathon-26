"""AWS Lambda handler for the pacs.008 CBPR+ generator.

Supports three invocation styles:
  1. Direct invocation:       event = {"count": 20, "error_rate": 0.3, ...}
  2. Function URL / API GW:   event["body"] = JSON string with the same fields
  3. Optional S3 upload:      "s3_bucket": "...", "s3_prefix": "runs/" in the event
                              (or env vars OUTPUT_BUCKET / OUTPUT_PREFIX)

Response: manifest (ground truth). XML inline only if include_xml=true AND
no S3 bucket is given (mind the 6 MB Lambda response limit).

Handler in AWS:  lambda_handler.lambda_handler
Runtime: Python 3.12 | Memory: 512 MB | Timeout: 60 s
"""
import json
import os

from pacs008_generator.generator import generate_batch


def _params(event):
    if isinstance(event, dict) and event.get("body"):
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        return body
    return event or {}


def _upload_to_s3(manifest, bucket, prefix):
    import boto3
    s3 = boto3.client("s3")
    base = "%s%s/" % (prefix, manifest["run_id"])
    for m in manifest["messages"]:
        s3.put_object(Bucket=bucket, Key=base + m["file"],
                      Body=m["xml"].encode("utf-8"),
                      ContentType="application/xml")
    slim = json.loads(json.dumps(manifest))
    for m in slim["messages"]:
        m.pop("xml", None)
    s3.put_object(Bucket=bucket, Key=base + "manifest.json",
                  Body=json.dumps(slim, indent=2, ensure_ascii=False).encode("utf-8"),
                  ContentType="application/json")
    return "s3://%s/%s" % (bucket, base)


def lambda_handler(event, context):
    p = _params(event)
    try:
        manifest = generate_batch(
            count=int(p.get("count", 10)),
            error_rate=float(p.get("error_rate", 0.3)),
            faulty=p.get("faulty"),
            seed=p.get("seed"),
            error_codes=p.get("error_codes"),
            write_files=False,
        )
    except (ValueError, AssertionError) as e:
        return {"statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": str(e)})}

    bucket = p.get("s3_bucket") or os.environ.get("OUTPUT_BUCKET")
    prefix = p.get("s3_prefix", os.environ.get("OUTPUT_PREFIX", "pacs008-runs/"))
    if bucket:
        manifest["s3_location"] = _upload_to_s3(manifest, bucket, prefix)
        include_xml = bool(p.get("include_xml", False))
    else:
        manifest["s3_location"] = None
        include_xml = bool(p.get("include_xml", True))
    if not include_xml:
        for m in manifest["messages"]:
            m.pop("xml", None)

    return {"statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(manifest, ensure_ascii=False)}
