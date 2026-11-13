#!/usr/bin/env python3
"""Choose the next GIF workflow step from an existing native Images job ledger.

This helper is offline. It never submits a request or generates fallback assets.
"""

import argparse
import json
from pathlib import Path
import re
import sys


ACTIVE_STATES = {"prepared", "submitting", "saving", "polling", "pending", "uncertain", "in_flight", "retry_wait"}
BLOCKING_MARKERS = (
    "content_policy", "policy violation", "safety", "moderation", "refusal", "content_filter", "违规", "安全策略",
    "invalid_api_key", "incorrect api key", "authentication", "unauthorized", "insufficient_quota", "rate limit", "billing", "额度", "余额",
)
UNSUPPORTED_PATTERNS = (
    r"\bgif\s+(?:output\s+)?(?:is\s+)?(?:not enabled|not supported|unsupported|not available|unavailable)\b",
    r"\b(?:unsupported|unavailable)\s+(?:output\s+)?(?:format\s*[:=]?\s*)?[\"']?gif\b",
    r"\bgif\s+preview\b.{0,80}\b(?:access (?:is )?required|not enabled|not available|not granted)\b",
    r"\brequires? access to (?:the )?gif preview\b",
)


def decide_native_job(record, *, native_only=False):
    def decision(action, reason, status=None):
        return {"action": action, "reason": reason, "fallback_allowed": action == "local_composition", "status": status,
                "default_order": ["native_gif", "local_composition"], "network_call_performed": False}

    if record.get("output_format") != "gif" or record.get("api") != "images":
        return decision("stop", "not_a_native_images_gif_job")
    state = record.get("state")
    if state in ACTIVE_STATES:
        return decision("recover", "native_job_not_terminal")
    if state == "completed" and record.get("ok") is True and record.get("outputs"):
        return decision("use_native_output", "native_output_validated_by_cli")
    if state == "completed":
        return decision("stop", "native_media_validation_failed")
    if state != "failed":
        return decision("stop", "unknown_native_job_state")
    attempts = record.get("attempts") or []
    last = attempts[-1] if attempts else {}
    status = last.get("status")
    if last.get("pending_image_result") or "read_error" in (last.get("error_kind") or ""):
        return decision("recover", "native_result_may_still_exist", status)
    # Use the final structured attempt, never an old attempt or the user's prompt.
    message = str(last.get("error") or "").lower()
    if status == 401 or any(marker in message for marker in BLOCKING_MARKERS):
        return decision("stop", "authentication_quota_or_safety_failure", status)
    if native_only:
        return decision("stop", "native_only_requested", status)
    if status in (400, 403, 422) and any(re.search(pattern, message) for pattern in UNSUPPORTED_PATTERNS):
        return decision("local_composition", "explicit_native_gif_capability_rejection", status)
    return decision("stop", "failure_does_not_establish_gif_unavailability", status)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-file", required=True, help="Existing cm_image_gen.py native GIF job ledger")
    parser.add_argument("--native-only", action="store_true", help="Respect an explicit no-fallback request")
    args = parser.parse_args(argv)
    try:
        record = json.loads(Path(args.job_file).read_text(encoding="utf-8-sig"))
        if not isinstance(record, dict):
            raise ValueError("Job ledger must contain an object")
        result = decide_native_job(record, native_only=args.native_only)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"action": "stop", "fallback_allowed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
