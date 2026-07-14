"""Generate a batch of pacs.008 messages and upload them to S3 payments/ prefix.

Usage (from repo root):
    pip install -r jobs/pacs008-generator/requirements.txt
    python jobs/pacs008-generator/aws/seed_s3.py \
        --bucket payinvestigator-mockdata-446643829639 \
        --count 10 \
        --error-rate 0.3 \
        --seed 42

Each uploaded file triggers S3 → SQS → Lambda ingest automatically.
"""
import argparse
import os
import sys

import boto3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pacs008_generator.generator import generate_batch


def main():
    ap = argparse.ArgumentParser(description="Seed S3 payments/ prefix with pacs.008 XML")
    ap.add_argument("--bucket", required=True, help="S3 bucket name")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--error-rate", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--prefix", default="payments/", help="S3 key prefix")
    ap.add_argument("--profile", default=None, help="AWS profile name")
    args = ap.parse_args()

    session = boto3.Session(profile_name=args.profile)
    s3 = session.client("s3")

    print("Generating %d messages (error_rate=%.0f%%)..." % (args.count, args.error_rate * 100))
    manifest = generate_batch(
        count=args.count,
        error_rate=args.error_rate,
        seed=args.seed,
        write_files=False,
    )

    run_id = manifest["run_id"]
    uploaded = 0
    for msg in manifest["messages"]:
        key = "%s%s/%s" % (args.prefix, run_id, msg["file"])
        s3.put_object(
            Bucket=args.bucket,
            Key=key,
            Body=msg["xml"].encode("utf-8"),
            ContentType="application/xml",
        )
        status = "FAULTY" if msg["is_faulty"] else "OK"
        errs = ", ".join(e["code"] for e in msg["errors"]) if msg["errors"] else "-"
        print("  uploaded %-40s  %s  %s" % (key, status, errs))
        uploaded += 1

    print("\nDone. %d files in s3://%s/%s%s/" % (uploaded, args.bucket, args.prefix, run_id))
    print("Run ID: %s" % run_id)


if __name__ == "__main__":
    main()
