"""Local job ledger and per-image provenance sidecars for cm-imagegen.

The ledger is written before the first chargeable submission and updated at every
state change, so an interrupted CLI process (for example a shell timeout) leaves a
record that `recover` can inspect instead of blindly resubmitting.

Ledgers live in `<out_dir>/.cm-jobs/` and may hold provider poll/result URLs; keep
them local. Sidecars (`<image>.cm.json`) omit URLs, base addresses and secrets so
they can travel with delivered images.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

JOB_DIR_NAME = ".cm-jobs"
SIDECAR_SUFFIX = ".cm.json"
LEDGER_VERSION = 1
TERMINAL_STATES = {"completed", "failed"}
# Read errors after a request was accepted: the provider may still finish and bill.
UNCERTAIN_ERROR_KINDS = {"images_read_error", "responses_read_error", "poll_url_error", "poll_os_error"}
# Fields that may carry addresses or signed URLs; never copied into sidecars.
PRIVATE_FIELDS = {"base_url", "request_url", "poll_candidates", "resolved_poll_url", "pid"}

_ACTIVE: "JobLedger | None" = None


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def new_job_id(filename: str | None) -> str:
    stem = Path(filename).stem if filename else "cm"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in stem).strip("-") or "cm"
    return f"{safe[:48]}-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


class JobLedger:
    def __init__(self, path: Path, record: dict):
        self.path = Path(path)
        self.record = record

    @classmethod
    def start(cls, out_dir: Path, *, job_file: str | None = None, **fields) -> "JobLedger":
        job_id = new_job_id(fields.get("filename"))
        path = Path(job_file) if job_file else Path(out_dir) / JOB_DIR_NAME / f"{job_id}.json"
        record = {
            "ledger_version": LEDGER_VERSION,
            "job_id": job_id,
            "state": "prepared",
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "pid": os.getpid(),
            "out_dir": str(Path(out_dir).resolve()),
            "submissions": 0,
            "attempts": [],
            **fields,
        }
        ledger = cls(path, record)
        ledger.write()
        return ledger

    @classmethod
    def load(cls, path: Path) -> "JobLedger":
        return cls(Path(path), json.loads(Path(path).read_text(encoding="utf-8")))

    def write(self) -> None:
        self.record["updated_at"] = now_iso()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.record, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def update(self, **fields) -> None:
        self.record.update(fields)
        self.write()

    def note_submission(self, attempt: int, endpoint: str) -> None:
        self.record["submissions"] = int(self.record.get("submissions") or 0) + 1
        self.update(state="submitting", current_attempt=attempt, endpoint=endpoint, submitted_at=now_iso())

    def note_attempt_error(
        self,
        attempt: int,
        message: str,
        status,
        *,
        will_retry: bool,
        error_kind: str | None = None,
        pending: bool = False,
    ) -> None:
        self.record.setdefault("attempts", []).append(
            {
                "attempt": attempt,
                "status": status,
                "error_kind": error_kind,
                "pending_image_result": bool(pending),
                "error": (message or "")[:500],
                "at": now_iso(),
            }
        )
        self.update(state="retry_wait" if will_retry else self.record.get("state", "submitting"))

    def exit_state(self) -> str:
        """Classify a run that ended without saved images."""
        attempts = self.record.get("attempts") or []
        last = attempts[-1] if attempts else {}
        kind = last.get("error_kind") or ""
        if self.record.get("state") == "polling" or last.get("pending_image_result"):
            return "pending"
        message = (last.get("error") or "").lower()
        if "partial_read" in kind or kind in UNCERTAIN_ERROR_KINDS or "timed out" in message or "timeout" in message:
            return "uncertain"
        return "failed"

    def finish_failed(self, message: str) -> None:
        state = self.exit_state()
        self.update(state=state, finished_at=now_iso(), exit_error=(message or "")[:1500])

    def note_polling(
        self, *, endpoint: str, transport: str, request_url: str, candidates: list[str], base_url: str | None = None
    ) -> None:
        fields = {
            "state": "polling",
            "endpoint": endpoint,
            "request_url": request_url,
            "poll_candidates": list(candidates),
        }
        if transport != "recover_poll":
            fields["transport"] = transport
        if base_url:
            fields["base_url"] = base_url
        self.update(**fields)


def set_active(ledger: JobLedger | None) -> None:
    global _ACTIVE
    _ACTIVE = ledger


def active() -> JobLedger | None:
    return _ACTIVE


def safe_call(method: str, *args, **kwargs) -> None:
    """Ledger bookkeeping must never break an image request."""
    ledger = _ACTIVE
    if ledger is None:
        return
    try:
        getattr(ledger, method)(*args, **kwargs)
    except Exception:
        pass


def output_records(paths: list[Path]) -> list[dict]:
    return [{"path": str(Path(p).resolve()), "sha256": sha256_file(Path(p))} for p in paths]


def sidecar_path(image_path: Path) -> Path:
    image_path = Path(image_path)
    return image_path.with_name(image_path.name + SIDECAR_SUFFIX)


def write_sidecars(record: dict, outputs: list[dict]) -> list[str]:
    public = {key: value for key, value in record.items() if key not in PRIVATE_FIELDS}
    written = []
    for index, output in enumerate(outputs):
        path = sidecar_path(Path(output["path"]))
        body = {
            **public,
            "output": output,
            "output_index": index,
            "sibling_outputs": [item["path"] for item in outputs if item is not output],
        }
        body.pop("outputs", None)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(path.resolve()))
    return written


def list_jobs(out_dir: Path) -> list[dict]:
    job_dir = Path(out_dir) / JOB_DIR_NAME
    if not job_dir.is_dir():
        return []
    jobs = []
    for path in sorted(job_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            jobs.append({"job_file": str(path.resolve()), "state": "unreadable"})
            continue
        jobs.append(
            {
                "job_file": str(path.resolve()),
                "job_id": record.get("job_id"),
                "command": record.get("command"),
                "state": record.get("state"),
                "filename": record.get("filename"),
                "submissions": record.get("submissions"),
                "started_at": record.get("started_at"),
                "updated_at": record.get("updated_at"),
                "terminal": record.get("state") in TERMINAL_STATES,
            }
        )
    return jobs


def candidate_outputs(record: dict) -> list[str]:
    """Image files in out_dir that match the job's filename and appeared after it started."""
    out_dir = Path(record.get("out_dir") or ".")
    filename = record.get("filename")
    if not filename or not out_dir.is_dir():
        return []
    stem = Path(filename).stem
    started = record.get("started_epoch") or 0
    found = []
    for path in out_dir.iterdir():
        if not path.is_file() or path.name.endswith(SIDECAR_SUFFIX):
            continue
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
            continue
        if path.stem == stem or path.stem.startswith(f"{stem}-"):
            if path.stat().st_mtime >= started - 1:
                found.append(str(path.resolve()))
    return sorted(found)
