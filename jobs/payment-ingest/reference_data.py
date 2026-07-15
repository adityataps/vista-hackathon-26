"""Loads optional reference data (BIC directory, sanctions watchlist, closed
accounts) from S3, at a location given by the REFERENCE_DATA_S3_URI env var
(e.g. "s3://payinvestigator-mockdata-<acct>/reference/").

Each object is expected to be a JSON array of strings:
  <prefix>bic_directory.json    -> valid/active BICs      (enables BIC_UNKNOWN)
  <prefix>watchlist.json        -> sanctioned party names  (enables SANCTIONS_NAME_HIT)
  <prefix>closed_accounts.json  -> closed account IBANs    (enables ACCOUNT_CLOSED)

If REFERENCE_DATA_S3_URI is unset, or an individual object is missing, the
corresponding check is simply skipped (logged as info) rather than failing
ingestion.
"""
import json
import logging
import os
from typing import List, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
_s3 = boto3.client("s3")


def _parse_s3_uri(uri: str):
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"REFERENCE_DATA_S3_URI must look like s3://bucket/prefix/, got: {uri}")
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return bucket, prefix


def _load_json_array(bucket: str, key: str) -> Optional[List[str]]:
    try:
        obj = _s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
        if isinstance(data, list):
            return data
        logger.warning("Reference data at s3://%s/%s is not a JSON array, ignoring.", bucket, key)
        return None
    except ClientError as exc:
        logger.info("Reference data s3://%s/%s not available: %s", bucket, key, exc)
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Reference data s3://%s/%s is not valid JSON: %s", bucket, key, exc)
        return None


def load_reference_data() -> dict:
    uri = os.environ.get("REFERENCE_DATA_S3_URI")
    if not uri:
        logger.info("REFERENCE_DATA_S3_URI not set - skipping BIC/watchlist/closed-account checks.")
        return {"known_bics": None, "watchlist": None, "closed_accounts": None}

    bucket, prefix = _parse_s3_uri(uri)
    bic_directory = _load_json_array(bucket, prefix + "bic_directory.json")
    return {
        "known_bics": set(bic_directory) if bic_directory else None,
        "watchlist": _load_json_array(bucket, prefix + "watchlist.json"),
        "closed_accounts": _load_json_array(bucket, prefix + "closed_accounts.json"),
    }
