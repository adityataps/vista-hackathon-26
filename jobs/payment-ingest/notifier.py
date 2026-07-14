"""POSTs a notification to a configurable HTTP endpoint when (and only when)
an error was detected on an ingested payment. Uses only the standard library
(urllib) so no extra dependency/layer is needed.

Endpoint is set via the ERROR_NOTIFY_ENDPOINT_URL env var; if unset, no POST
is attempted (and none is ever sent for error-free payments).
"""
import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def notify_payment_error(payment_id, error_msg: str) -> None:
    endpoint_url = os.environ.get("ERROR_NOTIFY_ENDPOINT_URL")
    if not endpoint_url:
        logger.info("ERROR_NOTIFY_ENDPOINT_URL not set - skipping error notification.")
        return

    timeout = int(os.environ.get("ERROR_NOTIFY_TIMEOUT_SECONDS", "5"))
    body = json.dumps({"payment_id": payment_id, "error_msg": error_msg}).encode("utf-8")
    request = urllib.request.Request(
        endpoint_url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            logger.info("notified %s about payment_id=%s error, status=%s", endpoint_url, payment_id, resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("error endpoint returned HTTP %s for payment_id=%s: %s", exc.code, payment_id, exc.read())
        raise
    except urllib.error.URLError as exc:
        logger.error("failed to reach error endpoint %s for payment_id=%s: %s", endpoint_url, payment_id, exc)
        raise
