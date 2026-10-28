import argparse
import base64
from dataclasses import dataclass
import importlib
import io
import hashlib
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "gpt-image-2.5-sunburst"
LEGACY_MODEL = "gpt-image-2"

# Official GPT Image 2.5 is published as two model families. Keep the short
# aliases explicit so `image2.5` never expands to the invalid generic ID
# `gpt-image-2.5`; callers can still pass an exact model or snapshot unchanged.
IMAGE_MODEL_ALIASES = {
    "image2.5": "gpt-image-2.5-sunburst",
    "gpt2.5": "gpt-image-2.5-sunburst",
    "image2.5-sunburst": "gpt-image-2.5-sunburst",
    "gpt2.5-sunburst": "gpt-image-2.5-sunburst",
    "image2.5-flare": "gpt-image-2.5-flare",
    "gpt2.5-flare": "gpt-image-2.5-flare",
}
DEFAULT_RESPONSES_MODEL = "gpt-5.4"
DEFAULT_SIZE = "1024x1024"
DEFAULT_RESPONSE_FORMAT = "b64_json"
PRIMARY_EXTRA_RETRY_ATTEMPTS = 2
PRIMARY_RETRY_DELAYS_SECONDS = (5, 15)
ERROR_BODY_PREVIEW_CHARS = 500
RESPONSE_READ_CHUNK_BYTES = 64 * 1024
MIN_ASYNC_POLL_WINDOW_SECONDS = 180
DEFAULT_ASYNC_POLL_INTERVAL_SECONDS = 2.0
TRANSPORT_PROBE_OUTPUT_DIR_NAME = "transport-probes"
SAFE_RESPONSE_HEADER_NAMES = {
    "content-type",
    "content-length",
    "date",
    "server",
    "via",
    "x-request-id",
    "request-id",
    "x-correlation-id",
    "x-trace-id",
    "x-openai-request-id",
    "cf-ray",
}
IMAGE_ENDPOINTS = {
    "generate": "/images/generations",
    "edit": "/images/edits",
}
PRIMARY_BASE_URL_FIELD = "CODEXMANAGER_IMAGE_BASE_URL"
PRIMARY_API_KEY_FIELD = "CODEXMANAGER_IMAGE_API_KEY"
LOCAL_CONFIG_DIR_NAME = "cm-imagegen"

# A requested 4K canvas must be verified against the bytes returned by the
# provider.  The provider may silently cap or reinterpret ``size``; this
# threshold makes such a response a failed generation instead of a false
# success.  Smaller/legacy requests stay warning-only unless callers opt in
# with ``--require-exact-size``.
FOUR_K_WIDTH = 3840
FOUR_K_HEIGHT = 2160


@dataclass(frozen=True)
class ImageApiProvider:
    name: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class ProviderRequestResult:
    data: dict
    endpoint: str
    transport: str
    request_url: str


@dataclass(frozen=True)
class InputImage:
    path: Path
    filename: str
    mime_type: str
    data: bytes

    def data_url(self) -> str:
        b64 = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime_type};base64,{b64}"


class ImageApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        raw: str | None = None,
        provider: str | None = None,
        diagnostics: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.raw = raw
        self.provider = provider
        self.diagnostics = diagnostics or {}
        self.attempt_failures: list[dict] = []


def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or home() / ".codex")


def normalize_image_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    for suffix in ["/responses", *IMAGE_ENDPOINTS.values()]:
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)].rstrip("/")
            break
    return base_url


def image_endpoint_path(command: str) -> str:
    try:
        return IMAGE_ENDPOINTS[command]
    except KeyError:
        raise SystemExit(f"Unknown image command: {command}")


def load_toml_basic(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    section = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = [part.strip().strip('"').strip("'") for part in line[1:-1].split(".") if part.strip()]
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        elif value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        cursor = data
        for part in section:
            cursor = cursor.setdefault(part, {})
        cursor[key] = value
    return data


def load_codex_config() -> dict:
    return load_toml_basic(codex_home() / "config.toml")


def load_auth_json() -> dict:
    auth_path = codex_home() / "auth.json"
    if auth_path.exists():
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            raise SystemExit(f"auth.json must contain a JSON object: {auth_path}")
        except Exception as exc:
            raise SystemExit(f"Failed to read auth.json: {exc}")
    return {}


def auth_value(*fields: str) -> str | None:
    data = load_auth_json()
    for field in fields:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def configured_provider() -> tuple[ImageApiProvider, str]:
    override = os.environ.get(PRIMARY_BASE_URL_FIELD)
    provider = {}
    if override and override.strip():
        base_url = override.strip()
        provider_name = "configured"
    else:
        config_path = codex_home() / "config.toml"
        cfg = load_codex_config()
        provider_name = str(cfg.get("model_provider") or "").strip()
        if not provider_name:
            raise SystemExit(f"No model_provider found in {config_path}.")
        providers = cfg.get("model_providers") or {}
        if not isinstance(providers, dict):
            raise SystemExit(f"No model_providers table found in {config_path}.")
        provider = providers.get(provider_name) or {}
        if not isinstance(provider, dict):
            raise SystemExit(f"model_provider {provider_name!r} is not defined in {config_path}.")
        base_url = str(provider.get("base_url") or "").strip()
        if not base_url:
            raise SystemExit(f"model_provider {provider_name!r} has no base_url in {config_path}.")

    api_key = os.environ.get(PRIMARY_API_KEY_FIELD)
    if api_key and api_key.strip():
        key = api_key.strip()
    elif isinstance(provider, dict):
        key = str(provider.get("api_key") or provider.get("key") or "").strip()
        env_name = str(provider.get("api_key_env_var") or provider.get("env_key") or "").strip()
        if not key and env_name:
            key = os.environ.get(env_name, "").strip()
        if not key:
            key = auth_value(PRIMARY_API_KEY_FIELD, "OPENAI_API_KEY") or ""
    else:
        key = auth_value(PRIMARY_API_KEY_FIELD, "OPENAI_API_KEY")
    if not key:
        raise SystemExit(f"No API key found for configured image provider in {codex_home() / 'auth.json'}.")
    return ImageApiProvider(provider_name, normalize_image_base_url(base_url), key), provider_name


def configured_responses_model(args: argparse.Namespace | None = None) -> str:
    if args and getattr(args, "responses_model", None):
        return args.responses_model
    env_model = os.environ.get("CODEXMANAGER_RESPONSES_MODEL")
    if env_model and env_model.strip():
        return env_model.strip()
    cfg_model = str(load_codex_config().get("model") or "").strip()
    return cfg_model or DEFAULT_RESPONSES_MODEL


def load_requests_module():
    try:
        return importlib.import_module("requests")
    except ImportError as exc:
        raise SystemExit(
            "The requests-based transport probe requires the 'requests' package in the current Python environment."
        ) from exc


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "-", name).strip(" .-")
    return name or f"image-{int(time.time())}"


def output_dir() -> Path:
    env = os.environ.get("CODEXMANAGER_IMAGE_OUTPUT_DIR")
    if env and env.strip():
        return Path(env.strip())
    return Path.cwd() / "generated-images"


def error_body_preview_chars() -> int:
    value = os.environ.get("CODEXMANAGER_IMAGE_ERROR_BODY_CHARS")
    if not value:
        return ERROR_BODY_PREVIEW_CHARS
    try:
        return max(0, min(int(value), 4000))
    except ValueError:
        return ERROR_BODY_PREVIEW_CHARS


def compact_text_preview(text: str, limit: int | None = None) -> str:
    limit = error_body_preview_chars() if limit is None else limit
    normalized = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}...<truncated {len(normalized) - limit} chars>"


def safe_response_headers(headers) -> dict:
    if not headers:
        return {}
    safe = {}
    for key, value in headers.items():
        key_l = str(key).lower()
        if key_l in SAFE_RESPONSE_HEADER_NAMES:
            safe[key_l] = compact_text_preview(str(value), 300)
    return safe


def classify_response_body(text: str) -> str:
    stripped = text.lstrip()
    if not stripped:
        return "empty"
    if looks_like_sse(stripped):
        return "sse_like"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json_like"
    if stripped[:20].lower().startswith("<!doctype html") or stripped[:10].lower().startswith("<html"):
        return "html_like"
    if "\ufffd" in stripped[:200]:
        return "binary_or_non_utf8"
    return "text_like"


def looks_like_sse(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("event:") or stripped.startswith("data:") or "\nevent:" in stripped[:1000]


def looks_like_base64_payload(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("data:") and ";base64," in stripped:
        return True
    if len(stripped) < 4:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]+", stripped):
        return False
    try:
        base64.b64decode(stripped, validate=True)
        return True
    except Exception:
        return False


def response_is_image_bytes(raw_bytes: bytes, headers, *, allow_partial: bool) -> bool:
    if allow_partial or not raw_bytes:
        return False
    content_type = safe_response_headers(headers).get("content-type") or ""
    content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type.startswith("image/"):
        return True
    return (
        raw_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        or raw_bytes.startswith(b"\xff\xd8")
        or (raw_bytes.startswith(b"RIFF") and b"WEBP" in raw_bytes[:16])
    )


def response_diagnostics(
    *,
    request_url: str,
    status: int | None,
    headers,
    raw_bytes: bytes,
    error_kind: str,
) -> dict:
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    header_map = safe_response_headers(headers)
    diagnostics = {
        "error_kind": error_kind,
        "request_url": request_url,
        "status": status,
        "headers": header_map,
        "content_type": header_map.get("content-type"),
        "content_length": header_map.get("content-length"),
        "body_bytes": len(raw_bytes),
        "body_chars": len(raw_text),
        "body_class": classify_response_body(raw_text),
        "body_preview": compact_text_preview(raw_text),
    }
    for request_id_key in ("x-request-id", "request-id", "x-correlation-id", "x-trace-id", "x-openai-request-id"):
        if request_id_key in header_map:
            diagnostics["request_id"] = header_map[request_id_key]
            break
    return diagnostics


def diagnostic_summary(diagnostics: dict) -> str:
    if not diagnostics:
        return ""
    parts = []
    for key in (
        "error_kind",
        "status",
        "content_type",
        "content_length",
        "body_bytes",
        "body_class",
        "request_id",
        "sse_event_count",
        "sse_json_payload_count",
        "sse_image_item_count",
    ):
        value = diagnostics.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    event_types = diagnostics.get("sse_event_types")
    if event_types:
        parts.append(f"sse_event_types={json.dumps(event_types, ensure_ascii=False)}")
    terminal = diagnostics.get("sse_terminal_evidence")
    if terminal:
        parts.append(f"sse_terminal_evidence={json.dumps(terminal, ensure_ascii=False, separators=(',', ':'))}")
    partial_read = diagnostics.get("partial_read_evidence")
    if partial_read:
        parts.append(f"partial_read_evidence={json.dumps(partial_read, ensure_ascii=False, separators=(',', ':'))}")
    preview = diagnostics.get("body_preview")
    if preview:
        parts.append(f"body_preview={preview}")
    return " ".join(parts)


def json_shape_diagnostics(data) -> dict:
    diagnostics = {
        "json_type": type(data).__name__,
        "likely_async_or_polling_response": False,
    }
    if isinstance(data, dict):
        keys = list(data.keys())
        diagnostics["top_level_keys"] = keys[:30]
        if len(keys) > 30:
            diagnostics["top_level_key_count"] = len(keys)
        for key in ("id", "object", "type", "status", "state", "task_id", "job_id", "request_id"):
            value = data.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                diagnostics[key] = value
        data_value = data.get("data")
        if isinstance(data_value, list):
            diagnostics["data_length"] = len(data_value)
        output_value = data.get("output")
        if isinstance(output_value, list):
            diagnostics["output_length"] = len(output_value)
        async_markers = {"status", "state", "task_id", "job_id", "poll_url", "result_url", "id"}
        status_value = str(data.get("status") or data.get("state") or "").lower()
        diagnostics["likely_async_or_polling_response"] = bool(
            async_markers.intersection(keys)
            and status_value in {"queued", "pending", "processing", "running", "submitted", "in_progress", ""}
            and not isinstance(data_value, list)
        )
    elif isinstance(data, list):
        diagnostics["list_length"] = len(data)
    try:
        diagnostics["json_preview"] = compact_text_preview(json.dumps(data, ensure_ascii=False), 1000)
    except TypeError:
        diagnostics["json_preview"] = compact_text_preview(str(data), 1000)
    return diagnostics


def json_string_matches(text: str, key: str) -> list[str]:
    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*"((?:[^"\\]|\\.)*)"')
    values = []
    for match in pattern.finditer(text):
        fragment = match.group(1)
        try:
            values.append(json.loads(f'"{fragment}"'))
        except json.JSONDecodeError:
            continue
    return values


def salvage_partial_image_response(text: str) -> tuple[dict | None, dict]:
    items = []
    seen = set()
    source_counts: dict[str, int] = {}

    def add_item(source: str, value: str, kind: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        key = (kind, normalized)
        if key in seen:
            return
        seen.add(key)
        items.append({kind: normalized})
        source_counts[source] = source_counts.get(source, 0) + 1

    for field in ("b64_json", "image_base64", "base64"):
        for value in json_string_matches(text, field):
            if looks_like_base64_payload(value):
                add_item(field, value, "b64_json")

    for value in json_string_matches(text, "url"):
        if value.startswith(("http://", "https://")):
            add_item("url", value, "url")

    for value in json_string_matches(text, "result"):
        if value.startswith(("http://", "https://")):
            add_item("result", value, "url")
        elif looks_like_base64_payload(value):
            add_item("result", value, "b64_json")

    diagnostics = {
        "partial_recovery_attempted": True,
        "partial_recovery_item_count": len(items),
        "partial_recovery_sources": source_counts,
    }
    if not items:
        return None, diagnostics
    return {"data": items}, diagnostics


def attach_partial_response_metadata(data: dict, diagnostics: dict | None) -> dict:
    if diagnostics:
        data["_cm_partial_response_salvaged"] = True
        data["_cm_partial_response_diagnostics"] = diagnostics
    return data


def attach_async_poll_metadata(data: dict, diagnostics: dict | None) -> dict:
    if diagnostics:
        data["_cm_async_poll_used"] = True
        data["_cm_async_poll_diagnostics"] = diagnostics
    return data


def no_image_items_error(
    *,
    provider: ImageApiProvider,
    endpoint: str,
    transport: str,
    request_url: str,
    data: dict,
) -> str:
    diagnostics = json_shape_diagnostics(data)
    message = (
        f"Images API returned no image items from {provider.name}/{cli_channel_label(provider)} "
        f"({request_url}) endpoint={endpoint} transport={transport}: "
        f"json_shape={json.dumps(diagnostics, ensure_ascii=False)}"
    )
    async_poll = data.get("_cm_async_poll_diagnostics") if isinstance(data, dict) else None
    if isinstance(async_poll, dict):
        message = f"{message} async_poll={json.dumps(async_poll, ensure_ascii=False)}"
    partial_response = data.get("_cm_partial_response_diagnostics") if isinstance(data, dict) else None
    if isinstance(partial_response, dict):
        message = f"{message} partial_response={json.dumps(partial_response, ensure_ascii=False)}"
    return message


def load_json_option(value: str, label: str, expected_type: type) -> object:
    path = Path(value).expanduser()
    raw = path.read_text(encoding="utf-8") if path.exists() else value
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} must be JSON or a path to a JSON file: {exc}")
    if not isinstance(data, expected_type):
        raise SystemExit(f"{label} must be a JSON {expected_type.__name__}.")
    return data


def image_tool_config(args: argparse.Namespace, image_model: str) -> list[dict]:
    if getattr(args, "tools", None):
        return load_json_option(args.tools, "--tools", list)
    tool = {
        "type": "image_generation",
        "model": image_model,
        "size": args.size,
        "action": "generate",
    }
    if args.quality:
        tool["quality"] = args.quality
    if args.background:
        tool["background"] = args.background
    if args.output_format:
        tool["output_format"] = args.output_format
    return [tool]


def responses_content(args: argparse.Namespace, input_images: list[InputImage] | None = None) -> list[dict]:
    content = [{"type": "input_text", "text": args.prompt}]
    for image in input_images or []:
        content.append({"type": "input_image", "image_url": image.data_url()})
    return content


def responses_payload(
    args: argparse.Namespace,
    image_model: str,
    input_images: list[InputImage] | None = None,
) -> tuple[dict, str]:
    responses_model = configured_responses_model(args)
    payload = {
        "model": responses_model,
        "input": [
            {
                "role": "user",
                "content": responses_content(args, input_images),
            }
        ],
        "tools": image_tool_config(args, image_model),
        "stream": True,
    }
    if not getattr(args, "tools", None):
        payload["tool_choice"] = {"type": "image_generation"}
    if getattr(args, "responses_reasoning", None):
        payload["reasoning"] = {"effort": args.responses_reasoning}
    if args.instructions:
        payload["instructions"] = args.instructions
    if args.responses_extra:
        extra = load_json_option(args.responses_extra, "--responses-extra", dict)
        payload.update(extra)
        payload["stream"] = True
    return payload, responses_model


def controller_defaults() -> dict:
    """Explicit user-selected image controller profile; never changes chat config."""
    path = codex_home() / LOCAL_CONFIG_DIR_NAME / "controller.json"
    if not path.exists():
        return {}
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(profile, dict) or profile.get("api") != "responses"
                or not isinstance(profile.get("responses_model"), str)
                or not profile["responses_model"].strip()
                or profile.get("responses_reasoning") not in {"low", "medium", "high", "xhigh", "max", "ultra"}):
            raise ValueError("invalid controller profile")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Invalid image controller profile: {path} ({type(exc).__name__})") from exc
    return {key: profile[key] for key in ("api", "responses_model", "responses_reasoning")}


def parse_sse_events(text: str) -> list[dict]:
    events = []
    event_name = None
    data_lines = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if event_name is not None or data_lines:
            events.append({"event": event_name, "data": "\n".join(data_lines)})
        event_name = None
        data_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line == "":
            flush()
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field, value = line.split(":", 1)
            if value.startswith(" "):
                value = value[1:]
        else:
            field, value = line, ""
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
    flush()
    return events


def sse_terminal_evidence(payloads: list[dict], event_counts: dict) -> dict:
    """Keep terminal facts only: no assistant text, prompts, errors or image bytes."""
    statuses = {"completed", "failed", "incomplete", "cancelled", "in_progress", "queued", "generating"}
    known_codes = {"content_policy_violation", "moderation_blocked", "safety_violation",
                   "image_generation_failed", "server_error", "rate_limit_exceeded", "invalid_request_error"}
    terminal_status = None
    tool_states = {}
    final_texts, done_texts, deltas = [], [], []
    explicit_refusal = any(name.startswith("response.refusal.") for name in event_counts)
    codes, unknown_code = set(), False

    def error_code(node):
        nonlocal unknown_code
        error = node.get("error")
        code = (error.get("code") or error.get("type")) if isinstance(error, dict) else None
        if code is None and node.get("type") == "error":
            code = node.get("code")
        if isinstance(code, str) and code:
            if code in known_codes:
                codes.add(code)
            else:
                unknown_code = True

    def message_text(node):
        nonlocal explicit_refusal
        texts = []
        if not isinstance(node, dict):
            return texts
        if node.get("type") == "refusal":
            explicit_refusal = True
        if node.get("type") == "message" and node.get("role") == "assistant":
            for part in node.get("content", []):
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    explicit_refusal = True
                value = part.get("text") if part.get("type") == "output_text" else part.get("refusal")
                if isinstance(value, str) and value:
                    texts.append(value)
        return texts

    for index, payload in enumerate(payloads):
        kind = payload.get("type", "")
        error_code(payload)
        if isinstance(kind, str) and kind.startswith("response.refusal."):
            explicit_refusal = True
        part = payload.get("part")
        if isinstance(part, dict) and part.get("type") == "refusal":
            explicit_refusal = True
        response = payload.get("response")
        if isinstance(response, dict):
            error_code(response)
            if isinstance(kind, str) and kind in {"response.completed", "response.failed", "response.incomplete", "response.cancelled"}:
                status = response.get("status")
                terminal_status = status if isinstance(status, str) and status in statuses else "other_or_missing"
                final_texts = [text for node in response.get("output", []) for text in message_text(node)]
            nodes = response.get("output", [])
        else:
            nodes = []
        item = payload.get("item")
        if isinstance(item, dict):
            nodes = [*nodes, item]
            if kind == "response.output_item.done":
                done_texts.extend(message_text(item))
        for node in nodes:
            if not isinstance(node, dict) or node.get("type") != "image_generation_call":
                continue
            error_code(node)
            status = node.get("status")
            tool_states[node.get("id") or f"item-{index}"] = {
                "status": status if isinstance(status, str) and status in statuses else "other_or_missing",
                "result_present": bool(node.get("result"))}
        if isinstance(kind, str) and kind.startswith("response.image_generation_call."):
            status = kind.rsplit(".", 1)[-1]
            tool_states[payload.get("item_id") or f"event-{index}"] = {
                "status": status if isinstance(status, str) and status in statuses else "other_or_missing",
                "result_present": bool(payload.get("result"))}
        if kind == "response.output_text.done" and isinstance(payload.get("text"), str):
            done_texts.append(payload["text"])
        if kind == "response.output_text.delta" and isinstance(payload.get("delta"), str):
            deltas.append(payload["delta"])
    source = "terminal_response" if final_texts else "completed_text" if done_texts else "delta_only" if deltas else "none"
    texts = final_texts or done_texts or (["".join(deltas)] if deltas else [])
    texts = list(dict.fromkeys(texts))
    assistant = "\n".join(texts)
    lower = assistant.lower().replace("\u2019", "'")
    phrases = {"cannot_help": "cannot help", "cant_help": "can't help", "cannot_generate": "cannot generate",
               "unable_generate": "unable to generate", "cant_generate": "can't generate",
               "zh_cannot_generate": "无法生成", "zh_cannot_provide": "不能提供", "zh_cannot_assist": "无法帮助"}
    phrase_labels = sorted(label for label, phrase in phrases.items() if phrase in lower)
    counts = {}
    for node in tool_states.values():
        label = node["status"]
        counts[label] = counts.get(label, 0) + 1
    return {"response_status": terminal_status,
            "terminal_event_counts": {name: event_counts[name] for name in
                ("response.completed", "response.failed", "response.incomplete", "response.cancelled") if event_counts.get(name)},
            "image_tool_status_counts": counts,
            "image_tool_result_present_count": sum(node["result_present"] for node in tool_states.values()),
            "safe_error_codes": sorted(codes), "unknown_error_code_present": unknown_code,
            "assistant_text_present": bool(assistant), "assistant_text_characters": len(assistant),
            "assistant_text_sha256": hashlib.sha256(assistant.encode("utf-8")).hexdigest() if assistant else None,
            "assistant_capture_source": source, "assistant_unique_complete_texts": len(texts),
            "explicit_rejection_observed": explicit_refusal, "possible_rejection_phrase_labels": phrase_labels,
            "rejection_state": "explicit_refusal" if explicit_refusal else "possible_text_rejection" if phrase_labels else "unknown",
            "raw_assistant_error_prompt_or_image_payload_saved": False}


def parse_sse_json_payloads(text: str) -> tuple[list[dict], dict]:
    events = parse_sse_events(text)
    payloads = []
    event_counts: dict[str, int] = {}
    invalid_json_count = 0
    done_count = 0
    for event in events:
        event_name = event.get("event") or "message"
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
        data = (event.get("data") or "").strip()
        if not data:
            continue
        if data == "[DONE]":
            done_count += 1
            continue
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            invalid_json_count += 1
            continue
        if isinstance(value, dict):
            if not value.get("type") and event_name in {"error", "response.completed", "response.failed", "response.incomplete", "response.cancelled"}:
                value = {**value, "type": event_name}
            payloads.append(value)
        else:
            payloads.append({"value": value})
    diagnostics = {
        "sse_event_count": len(events),
        "sse_event_types": event_counts,
        "sse_json_payload_count": len(payloads),
        "sse_invalid_json_count": invalid_json_count,
        "sse_done_count": done_count,
    }
    try:
        diagnostics["sse_terminal_evidence"] = sse_terminal_evidence(payloads, event_counts)
    except Exception:
        diagnostics["sse_terminal_evidence"] = {"extraction_failed": True}
    if payloads:
        diagnostics["sse_first_payload_shape"] = json_shape_diagnostics(payloads[0])
        diagnostics["sse_last_payload_shape"] = json_shape_diagnostics(payloads[-1])
    return payloads, diagnostics


def parsed_sse_image_response(text: str) -> tuple[dict | None, dict]:
    payloads, diagnostics = parse_sse_json_payloads(text)
    items = []
    seen = set()
    for payload in payloads:
        for item in response_image_items(payload):
            kind = "b64_json" if item.get("b64_json") else "url"
            identity = (kind, hashlib.sha256(item[kind].strip().encode("utf-8")).hexdigest())
            if identity not in seen:
                seen.add(identity)
                items.append(item)
    diagnostics["sse_image_item_count"] = len(items)
    if not items:
        return None, diagnostics
    return {
        "data": items,
        "output": payloads,
        "_cm_sse_parsed": True,
        "_cm_sse_diagnostics": diagnostics,
    }, diagnostics


def read_response_bytes(
    resp,
    *,
    provider: ImageApiProvider,
    request_url: str,
    status: int | None,
    headers,
    api_name: str,
) -> tuple[bytes, dict | None]:
    chunks = []
    while True:
        try:
            chunk = resp.read(RESPONSE_READ_CHUNK_BYTES)
        except OSError as exc:
            raw_bytes = b"".join(chunks)
            diagnostics = response_diagnostics(
                request_url=request_url,
                status=status,
                headers=headers,
                raw_bytes=raw_bytes,
                error_kind=f"{api_name.lower()}_partial_read_error" if raw_bytes else f"{api_name.lower()}_read_error",
            )
            diagnostics.update(
                {
                    "partial_response_salvage_attempted": bool(raw_bytes),
                    "read_exception_type": type(exc).__name__,
                    "read_exception": compact_text_preview(str(exc), 500),
                }
            )
            if not raw_bytes:
                raise ImageApiError(
                    f"Failed while reading response from {provider.name} {api_name} API: {exc}",
                    provider=provider.name,
                    diagnostics=diagnostics,
                )
            return raw_bytes, diagnostics
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks), None


def decode_json_or_sse_response(
    *,
    provider: ImageApiProvider,
    request_url: str,
    status: int | None,
    headers,
    raw_bytes: bytes,
    partial_diagnostics: dict | None = None,
) -> dict:
    if response_is_image_bytes(raw_bytes, headers, allow_partial=bool(partial_diagnostics)):
        data = {"data": [{"b64_json": base64.b64encode(raw_bytes).decode("ascii")}], "_cm_binary_image_response": True}
        return attach_partial_response_metadata(data, partial_diagnostics)

    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        return attach_partial_response_metadata(data, partial_diagnostics)
    except json.JSONDecodeError as exc:
        diagnostics = response_diagnostics(
            request_url=request_url,
            status=status,
            headers=headers,
            raw_bytes=raw_bytes,
            error_kind="invalid_json_success_response",
        )
        if looks_like_sse(raw):
            parsed, sse_diagnostics = parsed_sse_image_response(raw)
            diagnostics.update(sse_diagnostics)
            if parsed:
                diagnostics["error_kind"] = "sse_stream_parsed"
                # Successful streams may echo prompts, instructions and image bytes.
                # Export structural diagnostics only, never raw payload previews.
                diagnostics.pop("body_preview", None)
                for key in ("sse_first_payload_shape", "sse_last_payload_shape"):
                    if isinstance(diagnostics.get(key), dict):
                        diagnostics[key].pop("json_preview", None)
                parsed["_cm_sse_diagnostics"] = diagnostics
                return attach_partial_response_metadata(parsed, partial_diagnostics)
            diagnostics["error_kind"] = "sse_stream_without_image_items"
            if partial_diagnostics:
                exception_class = partial_diagnostics.get("read_exception_type")
                safe_exception_classes = {
                    "OSError", "TimeoutError", "ConnectionResetError", "ConnectionAbortedError",
                    "ConnectionRefusedError", "BrokenPipeError", "IncompleteRead", "RemoteDisconnected",
                    "ReadTimeout", "ReadTimeoutError", "ConnectTimeout", "ConnectionError",
                    "ChunkedEncodingError", "SSLError", "ProtocolError", "ContentDecodingError",
                }
                diagnostics["partial_read_evidence"] = {
                    "exception_class": exception_class if isinstance(exception_class, str)
                        and exception_class in safe_exception_classes else "other_or_missing",
                    "partial_bytes": len(raw_bytes),
                }
            # This failure path exports lifecycle facts, not response-body previews.
            for key in ("body_preview", "sse_first_payload_shape", "sse_last_payload_shape"):
                diagnostics.pop(key, None)
            raise ImageApiError(
                f"{provider.name} Images API returned SSE but no image items: {exc}",
                status=status,
                raw=raw,
                provider=provider.name,
                diagnostics=diagnostics,
            )
        if partial_diagnostics:
            diagnostics.update(partial_diagnostics)
            recovered, recovery_diagnostics = salvage_partial_image_response(raw)
            diagnostics.update(recovery_diagnostics)
            if recovered:
                diagnostics["error_kind"] = "partial_response_recovered"
                return attach_partial_response_metadata(recovered, diagnostics)
        raise ImageApiError(
            f"{provider.name} Images API returned invalid JSON: {exc}",
            status=status,
            raw=raw,
            provider=provider.name,
            diagnostics=diagnostics,
        )


def concise_api_error(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "empty error response"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:1000]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        parts = []
        for key in ("type", "code", "message"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{key}={value.strip()}")
        if parts:
            return " ".join(parts)[:1000]
    return json.dumps(data, ensure_ascii=False)[:1000]


def async_poll_interval_seconds() -> float:
    value = os.environ.get("CODEXMANAGER_IMAGE_ASYNC_POLL_INTERVAL")
    if not value:
        return DEFAULT_ASYNC_POLL_INTERVAL_SECONDS
    try:
        return max(0.1, min(float(value), 30.0))
    except ValueError:
        return DEFAULT_ASYNC_POLL_INTERVAL_SECONDS


def async_poll_window_seconds(timeout: int) -> int:
    value = os.environ.get("CODEXMANAGER_IMAGE_ASYNC_POLL_TIMEOUT")
    if value:
        try:
            return max(1, min(int(value), 3600))
        except ValueError:
            pass
    return max(int(timeout), MIN_ASYNC_POLL_WINDOW_SECONDS)


def poll_request_timeout(timeout: int) -> int:
    return max(15, min(int(timeout), 90))


def resolve_poll_url(provider: ImageApiProvider, request_url: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped.startswith(("http://", "https://")):
        return stripped
    if stripped.startswith("/"):
        return urllib.parse.urljoin(f"{provider.base_url}/", stripped.lstrip("/"))
    return urllib.parse.urljoin(f"{request_url.rstrip('/')}/", stripped)


def collect_string_fields(data, wanted_keys: set[str]) -> list[tuple[str, str]]:
    values = []

    def walk(value) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in wanted_keys and isinstance(child, str) and child.strip():
                    values.append((key, child.strip()))
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return values


def async_poll_candidates(
    data: dict,
    *,
    provider: ImageApiProvider,
    request_url: str,
    endpoint: str,
) -> list[str]:
    urls = []
    seen = set()

    def add(value: str) -> None:
        normalized = resolve_poll_url(provider, request_url, value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            urls.append(normalized)

    for _key, value in collect_string_fields(data, {"poll_url", "result_url"}):
        add(value)

    id_values = [value for _key, value in collect_string_fields(data, {"task_id", "job_id", "id"})]
    if endpoint == "/responses":
        for value in id_values:
            add(f"{provider.base_url}/responses/{urllib.parse.quote(value, safe='')}")
    else:
        for value in id_values:
            quoted = urllib.parse.quote(value, safe="")
            add(f"{provider.base_url}{endpoint}/{quoted}")

    return urls


def request_poll_url(provider: ImageApiProvider, url: str, timeout: int) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Accept": "application/json, text/event-stream, image/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            raw_bytes, partial_diagnostics = read_response_bytes(
                resp,
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                api_name="Poll",
            )
            return decode_json_or_sse_response(
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                partial_diagnostics=partial_diagnostics,
            )
    except urllib.error.HTTPError as exc:
        raw_bytes = exc.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        diagnostics = response_diagnostics(
            request_url=url,
            status=exc.code,
            headers=exc.headers,
            raw_bytes=raw_bytes,
            error_kind="poll_http_error_response",
        )
        raise ImageApiError(
            f"HTTP {exc.code} from {provider.name} poll API: {concise_api_error(raw)}",
            status=exc.code,
            raw=raw,
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except urllib.error.URLError as exc:
        diagnostics = {
            "error_kind": "poll_url_error",
            "request_url": url,
            "exception_type": type(exc.reason).__name__ if getattr(exc, "reason", None) else type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} poll API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except OSError as exc:
        diagnostics = {
            "error_kind": "poll_os_error",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed while reading response from {provider.name} poll API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )


def read_requests_stream_bytes(
    resp,
    *,
    provider: ImageApiProvider,
    request_url: str,
    status: int | None,
    api_name: str,
) -> tuple[bytes, dict | None]:
    chunks = []
    headers = getattr(resp, "headers", {})
    try:
        for chunk in resp.iter_content(chunk_size=RESPONSE_READ_CHUNK_BYTES):
            if chunk:
                chunks.append(chunk)
    except Exception as exc:
        raw_bytes = b"".join(chunks)
        diagnostics = response_diagnostics(
            request_url=request_url,
            status=status,
            headers=headers,
            raw_bytes=raw_bytes,
            error_kind=f"{api_name.lower()}_requests_partial_read_error"
            if raw_bytes
            else f"{api_name.lower()}_requests_read_error",
        )
        diagnostics.update(
            {
                "transport_client": "requests_stream",
                "partial_response_salvage_attempted": bool(raw_bytes),
                "read_exception_type": type(exc).__name__,
                "read_exception": compact_text_preview(str(exc), 500),
            }
        )
        if not raw_bytes:
            raise ImageApiError(
                f"Failed while reading response from {provider.name} {api_name} API via requests stream: {exc}",
                provider=provider.name,
                diagnostics=diagnostics,
            )
        return raw_bytes, diagnostics
    return b"".join(chunks), None


def request_poll_url_requests_stream(provider: ImageApiProvider, url: str, timeout: int) -> dict:
    requests = load_requests_module()
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Accept": "application/json, text/event-stream, image/*",
            },
            timeout=timeout,
            stream=True,
        )
    except Exception as exc:
        diagnostics = {
            "error_kind": "poll_requests_connect_error",
            "transport_client": "requests_stream",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} poll API via requests stream: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )

    try:
        status = getattr(resp, "status_code", None)
        raw_bytes, partial_diagnostics = read_requests_stream_bytes(
            resp,
            provider=provider,
            request_url=url,
            status=status,
            api_name="Poll",
        )
        if status and status >= 400:
            raw = raw_bytes.decode("utf-8", errors="replace")
            diagnostics = response_diagnostics(
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                error_kind="poll_requests_http_error_response",
            )
            diagnostics["transport_client"] = "requests_stream"
            raise ImageApiError(
                f"HTTP {status} from {provider.name} poll API via requests stream: {concise_api_error(raw)}",
                status=status,
                raw=raw,
                provider=provider.name,
                diagnostics=diagnostics,
            )
        return decode_json_or_sse_response(
            provider=provider,
            request_url=url,
            status=status,
            headers=resp.headers,
            raw_bytes=raw_bytes,
            partial_diagnostics=partial_diagnostics,
        )
    finally:
        try:
            resp.close()
        except Exception:
            pass


def maybe_poll_async_result(
    provider: ImageApiProvider,
    endpoint: str,
    transport: str,
    request_url: str,
    data: dict,
    timeout: int,
    *,
    poll_fetcher=None,
) -> dict:
    if response_image_items(data):
        return data

    initial_shape = json_shape_diagnostics(data)
    initial_candidates = async_poll_candidates(
        data,
        provider=provider,
        request_url=request_url,
        endpoint=endpoint,
    )
    if not initial_shape.get("likely_async_or_polling_response") and not initial_candidates:
        return data

    interval_seconds = async_poll_interval_seconds()
    deadline = time.time() + async_poll_window_seconds(timeout)
    current_url = initial_candidates[0] if initial_candidates else None
    queued_urls = initial_candidates[1:]
    attempt = 0
    diagnostics = {
        "triggered": True,
        "endpoint": endpoint,
        "transport": transport,
        "poll_client": getattr(poll_fetcher, "__name__", "urllib_poll") if poll_fetcher else "urllib_poll",
        "initial_shape": initial_shape,
        "initial_candidates": initial_candidates,
        "poll_interval_seconds": interval_seconds,
        "poll_window_seconds": async_poll_window_seconds(timeout),
        "attempts": [],
    }
    last_data = data
    poll_fetch = poll_fetcher or request_poll_url

    while current_url and time.time() <= deadline:
        attempt += 1
        try:
            polled = poll_fetch(provider, current_url, poll_request_timeout(timeout))
        except ImageApiError as exc:
            diagnostics["attempts"].append(
                {
                    "attempt": attempt,
                    "poll_url": current_url,
                    "error": exc.message,
                    "status": exc.status,
                    "diagnostics": exc.diagnostics,
                }
            )
            if time.time() + interval_seconds > deadline:
                break
            time.sleep(interval_seconds)
            continue

        poll_items = response_image_items(polled)
        polled_shape = json_shape_diagnostics(polled)
        diagnostics["attempts"].append(
            {
                "attempt": attempt,
                "poll_url": current_url,
                "image_item_count": len(poll_items),
                "shape": polled_shape,
                "parsed_sse_stream": bool(polled.get("_cm_sse_parsed")),
                "partial_response_salvaged": bool(polled.get("_cm_partial_response_salvaged")),
            }
        )
        if poll_items:
            diagnostics["completed"] = True
            diagnostics["resolved_poll_url"] = current_url
            diagnostics["attempt_count"] = attempt
            return attach_async_poll_metadata(polled, diagnostics)

        last_data = polled
        next_candidates = async_poll_candidates(
            polled,
            provider=provider,
            request_url=current_url,
            endpoint=endpoint,
        )
        if next_candidates:
            current_url = next_candidates[0]
            for candidate in next_candidates[1:]:
                if candidate not in queued_urls:
                    queued_urls.append(candidate)
        elif polled_shape.get("likely_async_or_polling_response"):
            pass
        elif queued_urls:
            current_url = queued_urls.pop(0)
        else:
            break

        if time.time() + interval_seconds > deadline:
            break
        time.sleep(interval_seconds)

    diagnostics["completed"] = False
    diagnostics["attempt_count"] = len(diagnostics["attempts"])
    return attach_async_poll_metadata(last_data, diagnostics)


def is_policy_or_safety_error(exc: ImageApiError) -> bool:
    terminal = exc.diagnostics.get("sse_terminal_evidence", {})
    policy_codes = {"content_policy_violation", "moderation_blocked", "safety_violation"}
    if terminal.get("explicit_rejection_observed") or policy_codes.intersection(terminal.get("safe_error_codes", [])):
        return True
    try:
        body = json.loads(exc.raw or "")
    except (ValueError, TypeError):
        body = None
    if isinstance(body, dict):
        for node in (body, body.get("response", {})):
            if not isinstance(node, dict):
                continue
            error = node.get("error", {})
            if isinstance(error, dict) and (error.get("code") in policy_codes or error.get("type") in policy_codes):
                return True
            if node.get("type") == "error" and node.get("code") in policy_codes:
                return True
    # Structured rejection evidence wins even when the gateway returns 5xx.
    if exc.diagnostics.get("error_kind") in {"sse_stream_without_image_items", "json_response_without_image_items"}:
        return False
    raw_text = f"{exc.raw or ''} {exc.message or ''}"
    if "<html" in raw_text[:2000].lower():
        return False
    raw = raw_text.lower()
    policy_markers = (
        "content_policy",
        "policy_violation",
        "policy violation",
        "violates policy",
        "safety policy",
        "moderation",
        "disallowed",
        "violate",
        "violat",
        "内容安全",
        "安全策略",
        "违规",
        "策略拒绝",
    )
    return any(marker in raw for marker in policy_markers)


def should_retry_primary_transport(exc: ImageApiError) -> bool:
    raw = f"{exc.raw or ''} {exc.message or ''}".lower()
    if is_policy_or_safety_error(exc):
        return False
    if exc.status in {400, 401, 403, 404, 409, 422}:
        return False
    terminal = exc.diagnostics.get("sse_terminal_evidence", {})
    if terminal.get("possible_rejection_phrase_labels") or "invalid_request_error" in terminal.get("safe_error_codes", []):
        return False
    if exc.diagnostics.get("pending_image_result"):
        return False
    if exc.diagnostics.get("error_kind") in {"sse_stream_without_image_items", "json_response_without_image_items"}:
        states = terminal.get("image_tool_status_counts", {})
        ended = terminal.get("response_status") in {"completed", "failed", "cancelled"}
        active = any(states.get(state) for state in ("in_progress", "queued", "generating"))
        zero_results = terminal.get("image_tool_result_present_count", 0) == 0
        if ended and zero_results and not active:
            if states.get("failed") or {"server_error", "rate_limit_exceeded"}.intersection(terminal.get("safe_error_codes", [])):
                return True
        # A complete empty compatibility result is a failed result, not an active job.
        return bool(exc.diagnostics.get("empty_compat_result"))
    if "partial_read" in exc.diagnostics.get("error_kind", "") or exc.diagnostics.get("partial_read_evidence"):
        return False
    if exc.diagnostics.get("error_kind") in {"images_read_error", "responses_read_error", "poll_url_error", "poll_os_error"}:
        return False
    transient_markers = (
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "remote end closed connection without response",
        "temporarily unavailable",
    )
    if exc.status in {408, 429, 500, 502, 503, 504}:
        return True
    return any(marker in raw for marker in transient_markers)


def require_image_result(result: ProviderRequestResult, provider: ImageApiProvider) -> None:
    """Classify complete JSON without an image inside the retry loop."""
    if response_image_items(result.data):
        return
    data = result.data
    status = data.get("status")
    event = f"response.{status}" if status in {"completed", "failed", "incomplete", "cancelled"} else "response.in_progress"
    terminal = sse_terminal_evidence([{"type": event, "response": data}], {event: 1})
    states = [value.lower() for _key, value in collect_string_fields(data, {"status", "state"})]
    diagnostics = {
        "error_kind": "json_response_without_image_items",
        "request_url": result.request_url,
        "sse_terminal_evidence": terminal,
        "pending_image_result": any(value in {"in_progress", "queued", "generating", "pending", "processing", "running"} for value in states),
        "empty_compat_result": data.get("data") == [] and not states and not data.get("error"),
    }
    raise ImageApiError("Image API returned a JSON response without image items.", provider=provider.name, diagnostics=diagnostics)


def retry_delay(attempt: int) -> None:
    time.sleep(PRIMARY_RETRY_DELAYS_SECONDS[min(attempt - 1, len(PRIMARY_RETRY_DELAYS_SECONDS) - 1)])


def retry_attempt_count(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--max-attempts must be an integer from 1 to 5") from exc
    if not 1 <= count <= 5:
        raise argparse.ArgumentTypeError("--max-attempts must be an integer from 1 to 5")
    return count


def format_provider_failures(failures: list[dict]) -> str:
    if not failures:
        return "Image request failed."
    compact = []
    for item in failures:
        attempt = item.get("attempt")
        attempt_text = f" attempt {attempt}" if attempt else ""
        api_provider = item.get("api_provider") or item.get("provider")
        api_channel = item.get("api_channel") or "unknown_channel"
        location = item.get("request_url") or item.get("base_url") or "unconfigured"
        status = item.get("status")
        status_text = f" status={status}" if status else ""
        diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), dict) else {}
        diagnostic_text = diagnostic_summary(diagnostics)
        diagnostic_suffix = f" diagnostics=[{diagnostic_text}]" if diagnostic_text else ""
        compact.append(
            f"{api_provider}/{api_channel}{attempt_text} ({location}){status_text}: "
            f"{item['error']}{diagnostic_suffix}"
        )
    return "Image request failed: " + " | ".join(compact)


def provider_name_value(provider: ImageApiProvider | str) -> str:
    return provider if isinstance(provider, str) else provider.name


def cli_provider_label(provider: ImageApiProvider | str) -> str:
    return provider_name_value(provider)


def cli_channel_label(provider: ImageApiProvider | str) -> str:
    return "configured_provider"


def failure_record(
    provider_name: str,
    base_url: str,
    phase: str,
    attempt: int | None,
    error: str,
    status: int | None,
    *,
    endpoint: str | None = None,
    transport: str | None = None,
    diagnostics: dict | None = None,
    api_channel: str | None = None,
) -> dict:
    request_url = f"{base_url}{endpoint}" if endpoint else None
    record = {
        "provider": provider_name,
        "api_provider": cli_provider_label(provider_name),
        "api_channel": api_channel or cli_channel_label(provider_name),
        "base_url": base_url,
        "endpoint": endpoint,
        "request_url": request_url,
        "transport": transport,
        "phase": phase,
        "attempt": attempt,
        "error": error,
        "status": status,
    }
    if diagnostics:
        record["diagnostics"] = diagnostics
    return record


def request_json(provider: ImageApiProvider, endpoint: str, payload: dict, timeout: int) -> dict:
    url = f"{provider.base_url}{endpoint}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            raw_bytes, partial_diagnostics = read_response_bytes(
                resp,
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                api_name="Images",
            )
            data = decode_json_or_sse_response(
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                partial_diagnostics=partial_diagnostics,
            )
            return maybe_poll_async_result(provider, endpoint, "images_json", url, data, timeout)
    except urllib.error.HTTPError as exc:
        raw_bytes = exc.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        diagnostics = response_diagnostics(
            request_url=url,
            status=exc.code,
            headers=exc.headers,
            raw_bytes=raw_bytes,
            error_kind="http_error_response",
        )
        raise ImageApiError(
            f"HTTP {exc.code} from {provider.name} Images API: {concise_api_error(raw)}",
            status=exc.code,
            raw=raw,
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except urllib.error.URLError as exc:
        diagnostics = {
            "error_kind": "url_error",
            "request_url": url,
            "exception_type": type(exc.reason).__name__ if getattr(exc, "reason", None) else type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} Images API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except OSError as exc:
        diagnostics = {
            "error_kind": "os_error",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed while reading response from {provider.name} Images API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )


def request_responses_provider(
    provider: ImageApiProvider,
    payload: dict,
    timeout: int,
) -> ProviderRequestResult:
    endpoint = "/responses"
    url = f"{provider.base_url}{endpoint}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            raw_bytes, partial_diagnostics = read_response_bytes(
                resp,
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                api_name="Responses",
            )
            data = decode_json_or_sse_response(
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                partial_diagnostics=partial_diagnostics,
            )
            data = maybe_poll_async_result(provider, endpoint, "responses_stream", url, data, timeout)
            return ProviderRequestResult(data, endpoint, "responses_stream", url)
    except urllib.error.HTTPError as exc:
        raw_bytes = exc.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        diagnostics = response_diagnostics(
            request_url=url,
            status=exc.code,
            headers=exc.headers,
            raw_bytes=raw_bytes,
            error_kind="responses_http_error_response",
        )
        raise ImageApiError(
            f"HTTP {exc.code} from {provider.name} Responses API: {concise_api_error(raw)}",
            status=exc.code,
            raw=raw,
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except urllib.error.URLError as exc:
        diagnostics = {
            "error_kind": "responses_url_error",
            "request_url": url,
            "exception_type": type(exc.reason).__name__ if getattr(exc, "reason", None) else type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} Responses API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except OSError as exc:
        diagnostics = {
            "error_kind": "responses_os_error",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed while reading response from {provider.name} Responses API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )


def multipart_body(fields: dict, files: list[dict]) -> tuple[bytes, str]:
    boundary = f"----cm-imagegen-{int(time.time() * 1000)}"
    chunks = []
    for key, value in fields.items():
        if value is None:
            continue
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for file_item in files:
        image = file_item["image"]
        field_name = file_item["field"]
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{image.filename}"\r\n'
                f"Content-Type: {image.mime_type}\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(image.data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), boundary


def request_multipart(
    provider: ImageApiProvider,
    endpoint: str,
    fields: dict,
    files: list[dict],
    timeout: int,
) -> dict:
    url = f"{provider.base_url}{endpoint}"
    body, boundary = multipart_body(fields, files)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            raw_bytes, partial_diagnostics = read_response_bytes(
                resp,
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                api_name="Images",
            )
            data = decode_json_or_sse_response(
                provider=provider,
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                partial_diagnostics=partial_diagnostics,
            )
            return maybe_poll_async_result(provider, endpoint, "images_multipart", url, data, timeout)
    except urllib.error.HTTPError as exc:
        raw_bytes = exc.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        diagnostics = response_diagnostics(
            request_url=url,
            status=exc.code,
            headers=exc.headers,
            raw_bytes=raw_bytes,
            error_kind="http_error_response",
        )
        raise ImageApiError(
            f"HTTP {exc.code} from {provider.name} Images API: {concise_api_error(raw)}",
            status=exc.code,
            raw=raw,
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except urllib.error.URLError as exc:
        diagnostics = {
            "error_kind": "url_error",
            "request_url": url,
            "exception_type": type(exc.reason).__name__ if getattr(exc, "reason", None) else type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} Images API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )
    except OSError as exc:
        diagnostics = {
            "error_kind": "os_error",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed while reading response from {provider.name} Images API: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )


def request_json_requests_stream(provider: ImageApiProvider, endpoint: str, payload: dict, timeout: int) -> dict:
    requests = load_requests_module()
    url = f"{provider.base_url}{endpoint}"
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Accept": "application/json, text/event-stream, image/*",
            },
            timeout=timeout,
            stream=True,
        )
    except Exception as exc:
        diagnostics = {
            "error_kind": "requests_connect_error",
            "transport_client": "requests_stream",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} Images API via requests stream: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )

    try:
        status = getattr(resp, "status_code", None)
        raw_bytes, partial_diagnostics = read_requests_stream_bytes(
            resp,
            provider=provider,
            request_url=url,
            status=status,
            api_name="Images",
        )
        if status and status >= 400:
            raw = raw_bytes.decode("utf-8", errors="replace")
            diagnostics = response_diagnostics(
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                error_kind="requests_http_error_response",
            )
            diagnostics["transport_client"] = "requests_stream"
            raise ImageApiError(
                f"HTTP {status} from {provider.name} Images API via requests stream: {concise_api_error(raw)}",
                status=status,
                raw=raw,
                provider=provider.name,
                diagnostics=diagnostics,
            )
        data = decode_json_or_sse_response(
            provider=provider,
            request_url=url,
            status=status,
            headers=resp.headers,
            raw_bytes=raw_bytes,
            partial_diagnostics=partial_diagnostics,
        )
        return maybe_poll_async_result(
            provider,
            endpoint,
            "images_json_requests_stream",
            url,
            data,
            timeout,
            poll_fetcher=request_poll_url_requests_stream,
        )
    finally:
        try:
            resp.close()
        except Exception:
            pass


def request_multipart_requests_stream(
    provider: ImageApiProvider,
    endpoint: str,
    fields: dict,
    files: list[dict],
    timeout: int,
) -> dict:
    requests = load_requests_module()
    url = f"{provider.base_url}{endpoint}"
    data_fields = {key: value for key, value in fields.items() if value is not None}
    file_parts = []
    for file_item in files:
        image = file_item["image"]
        file_parts.append((file_item["field"], (image.filename, image.data, image.mime_type)))
    try:
        resp = requests.post(
            url,
            data=data_fields,
            files=file_parts,
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Accept": "application/json, text/event-stream, image/*",
            },
            timeout=timeout,
            stream=True,
        )
    except Exception as exc:
        diagnostics = {
            "error_kind": "requests_connect_error",
            "transport_client": "requests_stream",
            "request_url": url,
            "exception_type": type(exc).__name__,
            "exception": compact_text_preview(str(exc), 500),
        }
        raise ImageApiError(
            f"Failed to reach {provider.name} Images API via requests stream: {exc}",
            provider=provider.name,
            diagnostics=diagnostics,
        )

    try:
        status = getattr(resp, "status_code", None)
        raw_bytes, partial_diagnostics = read_requests_stream_bytes(
            resp,
            provider=provider,
            request_url=url,
            status=status,
            api_name="Images",
        )
        if status and status >= 400:
            raw = raw_bytes.decode("utf-8", errors="replace")
            diagnostics = response_diagnostics(
                request_url=url,
                status=status,
                headers=resp.headers,
                raw_bytes=raw_bytes,
                error_kind="requests_http_error_response",
            )
            diagnostics["transport_client"] = "requests_stream"
            raise ImageApiError(
                f"HTTP {status} from {provider.name} Images API via requests stream: {concise_api_error(raw)}",
                status=status,
                raw=raw,
                provider=provider.name,
                diagnostics=diagnostics,
            )
        data = decode_json_or_sse_response(
            provider=provider,
            request_url=url,
            status=status,
            headers=resp.headers,
            raw_bytes=raw_bytes,
            partial_diagnostics=partial_diagnostics,
        )
        return maybe_poll_async_result(
            provider,
            endpoint,
            "images_multipart_requests_stream",
            url,
            data,
            timeout,
            poll_fetcher=request_poll_url_requests_stream,
        )
    finally:
        try:
            resp.close()
        except Exception:
            pass


def request_provider_requests_stream(
    provider: ImageApiProvider,
    command: str,
    endpoint: str,
    payload: dict,
    timeout: int,
    multipart: dict | None = None,
) -> ProviderRequestResult:
    if command == "edit" and multipart:
        data = request_multipart_requests_stream(provider, endpoint, multipart["fields"], multipart["files"], timeout)
        return ProviderRequestResult(data, endpoint, "images_multipart_requests_stream", f"{provider.base_url}{endpoint}")
    data = request_json_requests_stream(provider, endpoint, payload, timeout)
    return ProviderRequestResult(data, endpoint, "images_json_requests_stream", f"{provider.base_url}{endpoint}")


def request_provider(
    provider: ImageApiProvider,
    command: str,
    endpoint: str,
    payload: dict,
    timeout: int,
    multipart: dict | None = None,
) -> ProviderRequestResult:
    if command == "edit" and multipart:
        data = request_multipart(provider, endpoint, multipart["fields"], multipart["files"], timeout)
        return ProviderRequestResult(data, endpoint, "images_multipart", f"{provider.base_url}{endpoint}")
    data = request_json(provider, endpoint, payload, timeout)
    return ProviderRequestResult(data, endpoint, "images_json", f"{provider.base_url}{endpoint}")


def request_compat_with_provider(
    provider: ImageApiProvider,
    command: str,
    payload: dict,
    timeout: int,
    multipart: dict | None = None,
    *,
    phase: str = "request",
    retry_attempts: int = 0,
) -> tuple[dict, ImageApiProvider, str, str, str, list[dict]]:
    endpoint = image_endpoint_path(command)
    failures = []
    for attempt in range(1, retry_attempts + 2):
        try:
            result = request_provider(provider, command, endpoint, payload, timeout, multipart)
            require_image_result(result, provider)
            return result.data, provider, result.endpoint, result.transport, result.request_url, failures
        except ImageApiError as exc:
            failures.append(
                failure_record(
                    provider.name,
                    provider.base_url,
                    phase,
                    attempt,
                    exc.message,
                    exc.status,
                    endpoint=endpoint,
                    transport="images_multipart" if command == "edit" else "images_json",
                    diagnostics=exc.diagnostics,
                )
            )
            if attempt <= retry_attempts and should_retry_primary_transport(exc):
                retry_delay(attempt)
                continue
            exc.attempt_failures = failures
            raise
    raise ImageApiError("Compatibility image request failed without an error record.")


def request_with_retry(
    command: str,
    compat_payload: dict,
    timeout: int,
    multipart: dict | None = None,
    *,
    max_attempts: int = PRIMARY_EXTRA_RETRY_ATTEMPTS + 1,
) -> tuple[dict, ImageApiProvider, str, str, str, list[dict]]:
    primary, _provider_name = configured_provider()
    failures = []
    try:
        return request_compat_with_provider(
            primary,
            command,
            compat_payload,
            timeout,
            multipart,
            phase="primary_compat_call",
            retry_attempts=max_attempts - 1,
        )
    except ImageApiError as exc:
        if exc.attempt_failures:
            raise SystemExit(format_provider_failures(exc.attempt_failures))
        failures.append(
            failure_record(
                primary.name,
                primary.base_url,
                "primary_compat_call",
                None,
                exc.message,
                exc.status,
                endpoint=image_endpoint_path(command),
                transport="images_multipart" if command == "edit" else "images_json",
                diagnostics=exc.diagnostics,
            )
        )
        raise SystemExit(format_provider_failures(failures))
    raise SystemExit(format_provider_failures(failures))


def request_responses_with_retry(
    payload: dict,
    timeout: int,
    *,
    max_attempts: int = PRIMARY_EXTRA_RETRY_ATTEMPTS + 1,
) -> tuple[dict, ImageApiProvider, str, str, str, list[dict]]:
    provider, _provider_name = configured_provider()
    failures = []
    endpoint = "/responses"
    for attempt in range(1, max_attempts + 1):
        try:
            result = request_responses_provider(provider, payload, timeout)
            require_image_result(result, provider)
            return result.data, provider, result.endpoint, result.transport, result.request_url, failures
        except ImageApiError as exc:
            failures.append(
                failure_record(
                    provider.name,
                    provider.base_url,
                    "primary_responses_call",
                    attempt,
                    exc.message,
                    exc.status,
                    endpoint=endpoint,
                    transport="responses_stream",
                    diagnostics=exc.diagnostics,
                    api_channel="configured_provider_responses",
                )
            )
            if attempt < max_attempts and should_retry_primary_transport(exc):
                retry_delay(attempt)
                continue
            raise SystemExit(format_provider_failures(failures))
    raise SystemExit(format_provider_failures(failures))


def load_input_image(path: Path, label: str) -> InputImage:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
    return InputImage(path.resolve(), path.name, mime_type, path.read_bytes())


def download_url_image(url: str, provider: ImageApiProvider | None) -> bytes:
    header_sets = [
        {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0",
        }
    ]
    if provider:
        header_sets.append(
            {
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Authorization": f"Bearer {provider.api_key}",
                "User-Agent": "Mozilla/5.0",
            }
        )
    errors = []
    for headers in header_sets:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            errors.append(f"HTTP {exc.code}")
        except urllib.error.URLError as exc:
            errors.append(str(exc))
    raise SystemExit(f"Failed to download URL image response: {'; '.join(errors)}")


def response_image_items(data: dict) -> list[dict]:
    direct_items = data.get("data")
    if isinstance(direct_items, list) and direct_items:
        items = []
        for item in direct_items:
            if isinstance(item, dict) and (item.get("b64_json") or item.get("url")):
                items.append(item)
        if items:
            return items

    items = []

    def walk(value) -> None:
        if isinstance(value, dict):
            item_type = str(value.get("type") or "")
            result = value.get("result")
            if "image_generation" in item_type and isinstance(result, str) and result.strip():
                result_value = result.strip()
                if result_value.startswith(("http://", "https://")):
                    items.append({"url": result_value})
                else:
                    items.append({"b64_json": result_value})
                return
            b64 = value.get("b64_json") or value.get("image_base64") or value.get("base64")
            if isinstance(b64, str) and b64.strip():
                items.append({"b64_json": b64.strip()})
                return
            url = value.get("url")
            if isinstance(url, str) and url.strip():
                items.append({"url": url.strip()})
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data.get("output", data))
    return items


def decode_base64_image(value: str) -> bytes:
    b64 = value.strip()
    if b64.startswith("data:") and "," in b64:
        b64 = b64.split(",", 1)[1].strip()
    return base64.b64decode(b64)


def parse_requested_size(value: str | None) -> tuple[int, int] | None:
    """Parse an API size such as ``3840x2160`` without changing its value."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", value)
    if not match:
        return None
    width, height = (int(part) for part in match.groups())
    if width <= 0 or height <= 0:
        return None
    return width, height


def parse_image_dimensions(raw: bytes) -> tuple[int, int] | None:
    """Read actual file dimensions; never transform or resample image bytes."""
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        return None
    data = bytes(raw)
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        # PNG IHDR is always first, has 13 data bytes and a 4-byte CRC.
        if len(data) < 33 or data[8:12] != b"\x00\x00\x00\x0d" or data[12:16] != b"IHDR":
            return None
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return (width, height) if width > 0 and height > 0 else None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
        return (int(width), int(height)) if width > 0 and height > 0 else None
    except Exception:
        # Strict mode fails closed when a format cannot be inspected.
        return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    """Read dimensions from a saved output path; unreadable files return None."""
    try:
        return parse_image_dimensions(path.read_bytes())
    except OSError:
        return None


def exact_size_is_required(requested_size: str | None, explicit: bool = False) -> bool:
    """Strictly verify explicit opt-in and native 4K-or-larger requests."""
    requested = parse_requested_size(requested_size)
    if explicit or requested is None:
        return bool(explicit)
    width, height = requested
    return max(width, height) >= FOUR_K_WIDTH or width * height >= FOUR_K_WIDTH * FOUR_K_HEIGHT


def validate_output_sizes(
    paths: list[Path], requested_size: str | None, *, require_exact: bool = False
) -> dict:
    """Inspect files and return serializable size metadata and diagnostics."""
    expected = parse_requested_size(requested_size)
    dimensions: list[str | None] = []
    warnings: list[dict] = []
    for path in paths:
        actual = image_dimensions(path)
        dimensions.append(f"{actual[0]}x{actual[1]}" if actual else None)
        if actual is None:
            warnings.append({"path": str(path.resolve()), "warning": "image_dimensions_unreadable"})
        elif expected and actual != expected:
            warnings.append({
                "path": str(path.resolve()),
                "warning": "image_size_mismatch",
                "expected": f"{expected[0]}x{expected[1]}",
                "actual": f"{actual[0]}x{actual[1]}",
            })
    if require_exact and expected is None:
        warnings.append({"warning": "exact_size_requires_explicit_dimensions"})
    mismatch = bool(warnings)
    strict_failure = bool(require_exact and (not paths or mismatch))
    return {
        "requested_size": requested_size,
        "output_dimensions": dimensions,
        "size_verified": (bool(paths) and not mismatch) if expected else None,
        "size_validation_warnings": warnings,
        "size_validation_strict": bool(require_exact),
        "size_validation_failed": strict_failure,
    }


def save_image_from_item(
    item: dict,
    out_dir: Path,
    filename: str | None,
    index: int,
    provider: ImageApiProvider | None = None,
) -> Path:
    b64 = item.get("b64_json")
    url = item.get("url")
    if isinstance(b64, str) and b64.strip():
        raw = decode_base64_image(b64)
    elif isinstance(url, str) and url.strip():
        raw = download_url_image(url.strip(), provider)
    else:
        raise SystemExit("Response item has neither b64_json nor url.")
    ext = ".png"
    if raw.startswith(b"\xff\xd8"):
        ext = ".jpg"
    elif raw.startswith(b"RIFF") and b"WEBP" in raw[:16]:
        ext = ".webp"
    base = sanitize_filename(filename or f"codexmanager-image-{int(time.time())}")
    if not base.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        base = f"{base}{ext}"
    if index > 0:
        stem = Path(base).stem
        suffix = Path(base).suffix
        base = f"{stem}-{index + 1}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / base
    if path.exists():
        stem = path.stem
        suffix = path.suffix
        path = out_dir / f"{stem}-{int(time.time())}{suffix}"
    path.write_bytes(raw)
    return path


def image_model_selection(args: argparse.Namespace) -> dict:
    """Keep the image tool model independent from the Responses controller."""
    requested = (getattr(args, "model", None) or "").strip()
    env_model = os.environ.get("CODEXMANAGER_IMAGE_MODEL", "").strip()
    raw = requested or env_model or DEFAULT_MODEL
    # Version shorthand is only a candidate ID, not proof of provider support.
    normalized = re.sub(r"[ _]+", "-", raw.strip().lower())
    model = IMAGE_MODEL_ALIASES.get(normalized)
    if model is None:
        alias = re.fullmatch(r"(?:image|gpt)[ -]?(\d+(?:\.\d+)*)", raw, re.IGNORECASE)
        model = f"gpt-image-{alias.group(1)}" if alias else raw
    return {
        "requested_model": requested or None,
        "image_model": model,
        "image_model_source": "cli" if requested else "environment" if env_model else "default",
        "model_alias_applied": model != raw,
    }


def model_catalog_check(provider: ImageApiProvider, model: str) -> dict:
    """Read-only preflight: never generate or silently substitute another model."""
    url = f"{provider.base_url}/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {provider.api_key}", "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
        entries = data.get("data") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ValueError("missing data list")
        ids = sorted({item["id"] for item in entries
                      if isinstance(item, dict) and isinstance(item.get("id"), str)})
    except (OSError, ValueError) as exc:
        # Do not expose response bodies, authorization headers or credentials.
        return {"ok": False, "model": model, "status": "catalog_unavailable",
                "error": f"Model catalog check failed ({type(exc).__name__}); no image request sent."}
    found = model in ids
    result = {"ok": found, "model": model, "status": "listed" if found else "not_listed",
              "listed_models": ids}
    if not found:
        result["error"] = f"Image model {model!r} is not listed by this provider; no image request sent."
    return result


def is_loopback_provider(provider: ImageApiProvider) -> bool:
    """Return True for a local gateway that owns its model/route catalog."""
    try:
        host = urllib.parse.urlparse(provider.base_url).hostname
    except ValueError:
        return False
    return host in {"127.0.0.1", "localhost", "::1"}


def image_payload(args: argparse.Namespace) -> tuple[dict, str]:
    selection = image_model_selection(args)
    model = selection["image_model"]
    # The Images API exposes the image model as its top-level `model`, so its
    # catalog can be checked before submission. Responses is different: the
    # top-level model is the mainline controller and the image model lives in
    # tools[].model. Some OpenAI-compatible gateways intentionally list only
    # mainline models at /models, so requiring the tool model to be listed
    # would reject a valid Responses request before it reaches the gateway.
    api = getattr(args, "api", "images")
    if api != "responses" and (getattr(args, "check_model", False) or model != LEGACY_MODEL):
        provider, _ = configured_provider()
        # A local CodexManager gateway validates its own V2 model routes. Its
        # /models response intentionally contains the mainline text catalog,
        # not every image-only route, so do not reject a configured local
        # image route solely because the tool model is absent from that list.
        if getattr(args, "check_model", False) or not is_loopback_provider(provider):
            check = model_catalog_check(provider, model)
            if not check["ok"]:
                raise SystemExit(check["error"])
    payload = {
        "model": model,
        "prompt": args.prompt,
        "size": args.size,
        "response_format": args.response_format,
    }
    if args.n is not None:
        payload["n"] = args.n
    if args.quality:
        payload["quality"] = args.quality
    if args.background:
        payload["background"] = args.background
    if args.output_format:
        payload["output_format"] = args.output_format
    return payload, model


def operation_names(value: str) -> list[str]:
    if value == "all":
        return ["generate", "edit"]
    return [value]


def route_preview(base_url: str, api: str, operation: str) -> dict:
    if api == "responses":
        endpoint = "/responses"
        transport = "responses_stream"
    else:
        endpoint = image_endpoint_path(operation)
        transport = "images_multipart" if operation == "edit" else "images_json"
    return {
        "operation": operation,
        "endpoint": endpoint,
        "transport": transport,
        "request_url": f"{base_url}{endpoint}",
    }


def payload_shape_preview(args: argparse.Namespace, api: str, operation: str, model: str) -> dict:
    prompt_present = bool(getattr(args, "prompt", None))
    if api == "responses":
        shape = {
            "operation": operation,
            "api": "responses",
            "content_type": "application/json",
            "top_level_fields": ["model", "input", "tools", "tool_choice", "stream"] + (["reasoning"] if getattr(args, "responses_reasoning", None) else []),
            "tool_choice": {"type": "image_generation"},
            "outer_model_source": "resolved_from_cli_or_controller_profile_or_environment_or_config",
            "outer_model": configured_responses_model(args),
            "reasoning_effort": getattr(args, "responses_reasoning", None),
            "stream": True,
            "prompt_text_included": prompt_present,
            "prompt_text_redacted": prompt_present,
            "input_image_bytes_included": operation == "edit",
            "input_image_bytes_redacted": operation == "edit",
            "tool_fields": {
                "type": "image_generation",
                "model": model,
                "size": getattr(args, "size", DEFAULT_SIZE),
                "action": "generate",
            },
        }
        for field in ("quality", "background", "output_format"):
            value = getattr(args, field, None)
            if value:
                shape["tool_fields"][field] = value
        return shape

    common_fields = {
        "model": model,
        "prompt": "<redacted>" if prompt_present else "<provided at request time>",
        "size": getattr(args, "size", DEFAULT_SIZE),
        "response_format": getattr(args, "response_format", DEFAULT_RESPONSE_FORMAT),
    }
    for field in ("n", "quality", "background", "output_format"):
        value = getattr(args, field, None)
        if value is not None:
            common_fields[field] = value
    if operation == "edit":
        return {
            "operation": operation,
            "api": "images",
            "content_type": "multipart/form-data",
            "form_fields": common_fields,
            "image_file_parts": "<redacted>",
            "mask_file_part": "<redacted if provided>",
        }
    return {
        "operation": operation,
        "api": "images",
        "content_type": "application/json",
        "json_fields": common_fields,
    }


def provider_doctor_status(
    provider: ImageApiProvider,
    *,
    api_channel: str,
    api: str,
    operations: list[str],
) -> dict:
    return {
        "ok": True,
        "configured": True,
        "api_provider": cli_provider_label(provider),
        "api_channel": api_channel,
        "base_url": provider.base_url,
        "api_key_present": bool(provider.api_key),
        "routes": [route_preview(provider.base_url, api, operation) for operation in operations],
    }


def doctor(args: argparse.Namespace) -> int:
    operations = operation_names(args.operation)
    selection = image_model_selection(args)
    model = selection["image_model"]
    show_payload_shape = bool(getattr(args, "show_payload_shape", False))
    result = {
        "ok": True,
        "operation": getattr(args, "command", None) or "doctor",
        "execution_channel": "cm_image_gen_cli",
        "skill_primary_channel": "cm_image_gen_cli",
        "network_call_performed": False,
        "api": args.api,
        "default_api": controller_defaults().get("api", "responses"),
        "commands": operations,
        "image_model": model,
        **selection,
        "model_semantics": "Image model requested by the CLI; gateway Responses controller and actual upstream execution are separate.",
        "payload_shape_included": show_payload_shape,
        "codex_home": str(codex_home()),
    }
    if show_payload_shape:
        result["payload_shapes"] = [
            payload_shape_preview(args, args.api, operation, model) for operation in operations
        ]
    if args.api == "responses":
        result["responses_model"] = configured_responses_model(args)
        result["responses_reasoning"] = getattr(args, "responses_reasoning", None)

    try:
        primary, _provider_name = configured_provider()
        api_channel = "configured_provider_responses" if args.api == "responses" else cli_channel_label(primary)
        result["configured_provider"] = provider_doctor_status(
            primary,
            api_channel=api_channel,
            api=args.api,
            operations=operations,
        )
        if getattr(args, "check_model", False):
            result["network_call_performed"] = True
            # For Responses, validate the top-level controller model. The
            # image tool model is intentionally not required to appear in the
            # gateway's mainline /models catalog.
            catalog_model = (
                configured_responses_model(args)
                if args.api == "responses"
                else model
            )
            result["model_catalog_check"] = model_catalog_check(primary, catalog_model)
            result["model_catalog_check"]["image_tool_model"] = model
            result["ok"] = result["model_catalog_check"]["ok"]
    except SystemExit as exc:
        result["ok"] = False
        result["configured_provider"] = {
            "ok": False,
            "configured": False,
            "error": str(exc),
        }


    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def transport_probe_client_names(value: str) -> list[str]:
    if value == "both":
        return ["urllib", "requests_stream"]
    if value == "requests":
        return ["requests_stream"]
    return [value]


def transport_probe_provider(args: argparse.Namespace) -> ImageApiProvider:
    provider, _provider_name = configured_provider()
    return provider


def probe_output_dir(args: argparse.Namespace) -> Path:
    if args.out_dir:
        return Path(args.out_dir)
    return output_dir() / TRANSPORT_PROBE_OUTPUT_DIR_NAME


def summarize_probe_success(
    *,
    client_name: str,
    provider: ImageApiProvider,
    result: ProviderRequestResult,
    data: dict,
    started_at: float,
    saved_paths: list[Path],
) -> dict:
    items = response_image_items(data)
    probe = {
        "client": client_name,
        "ok": True,
        "duration_ms": int((time.time() - started_at) * 1000),
        "api_provider": cli_provider_label(provider),
        "api_channel": cli_channel_label(provider),
        "base_url": provider.base_url,
        "endpoint": result.endpoint,
        "transport": result.transport,
        "request_url": result.request_url,
        "image_item_count": len(items),
        "parsed_sse_stream": bool(data.get("_cm_sse_parsed")),
        "partial_response_salvaged": bool(data.get("_cm_partial_response_salvaged")),
        "async_poll_used": bool(data.get("_cm_async_poll_used")),
    }
    if data.get("_cm_sse_diagnostics"):
        probe["sse_diagnostics"] = data.get("_cm_sse_diagnostics")
    if data.get("_cm_partial_response_diagnostics"):
        probe["partial_response_diagnostics"] = data.get("_cm_partial_response_diagnostics")
    if data.get("_cm_async_poll_diagnostics"):
        probe["async_poll_diagnostics"] = data.get("_cm_async_poll_diagnostics")
    if saved_paths:
        probe["saved_paths"] = [str(path.resolve()) for path in saved_paths]
    return probe


def summarize_probe_failure(
    *,
    client_name: str,
    provider: ImageApiProvider,
    endpoint: str,
    transport: str,
    started_at: float,
    exc: Exception,
) -> dict:
    if isinstance(exc, ImageApiError):
        error = exc.message
        status = exc.status
        diagnostics = exc.diagnostics
    else:
        error = str(exc)
        status = None
        diagnostics = {}
    return {
        "client": client_name,
        "ok": False,
        "duration_ms": int((time.time() - started_at) * 1000),
        "api_provider": cli_provider_label(provider),
        "api_channel": cli_channel_label(provider),
        "base_url": provider.base_url,
        "endpoint": endpoint,
        "transport": transport,
        "request_url": f"{provider.base_url}{endpoint}",
        "status": status,
        "error": error,
        "diagnostics": diagnostics,
    }


def transport_probe(args: argparse.Namespace) -> int:
    provider = transport_probe_provider(args)
    command = args.operation
    payload, model = image_payload(args)
    endpoint = image_endpoint_path(command)
    input_images: list[InputImage] = []
    multipart = None

    if command == "edit":
        if not args.image:
            raise SystemExit("--image is required for transport-probe --operation edit.")
        image_paths = [Path(value).expanduser() for value in args.image]
        input_images = [load_input_image(image_path, "Input image") for image_path in image_paths]
        mask_path = Path(args.mask).expanduser() if args.mask else None
        mask_image = load_input_image(mask_path, "Mask image") if mask_path else None
        multipart_fields = {
            "model": model,
            "prompt": args.prompt,
            "size": args.size,
            "response_format": args.response_format,
            "n": args.n,
            "quality": args.quality,
            "background": args.background,
            "output_format": args.output_format,
        }
        multipart_files = [{"field": "image", "image": image} for image in input_images]
        if mask_image:
            multipart_files.append({"field": "mask", "image": mask_image})
        multipart = {"fields": multipart_fields, "files": multipart_files}

    clients = transport_probe_client_names(args.client)
    probes = []
    for client_name in clients:
        started_at = time.time()
        transport = "images_multipart" if command == "edit" else "images_json"
        if client_name == "requests_stream":
            transport = f"{transport}_requests_stream"
        try:
            if client_name == "urllib":
                result = request_provider(provider, command, endpoint, payload, args.timeout, multipart)
            elif client_name == "requests_stream":
                result = request_provider_requests_stream(provider, command, endpoint, payload, args.timeout, multipart)
            else:
                raise SystemExit(f"Unknown transport probe client: {client_name}")

            saved_paths: list[Path] = []
            if args.save_images:
                out_dir = probe_output_dir(args)
                items = response_image_items(result.data)
                base_name = args.filename or f"transport-probe-{provider.name}-{command}-{client_name}"
                saved_paths = [
                    save_image_from_item(item, out_dir, base_name, index, provider) for index, item in enumerate(items)
                ]
            probes.append(
                summarize_probe_success(
                    client_name=client_name,
                    provider=provider,
                    result=result,
                    data=result.data,
                    started_at=started_at,
                    saved_paths=saved_paths,
                )
            )
        except (ImageApiError, SystemExit) as exc:
            probes.append(
                summarize_probe_failure(
                    client_name=client_name,
                    provider=provider,
                    endpoint=endpoint,
                    transport=transport,
                    started_at=started_at,
                    exc=exc,
                )
            )

    result = {
        "ok": any(item.get("ok") for item in probes),
        "operation": "transport-probe",
        "skill_primary_channel": "cm_image_gen_cli",
        "execution_channel": "cm_image_gen_cli",
        "api": "images",
        "probe_provider": "configured",
        "endpoint": endpoint,
        "command": command,
        "model": model,
        "size": args.size,
        "response_format": args.response_format,
        "clients": probes,
    }
    if input_images:
        result["source_images"] = [str(image.path) for image in input_images]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def generate(args: argparse.Namespace) -> int:
    payload, model = image_payload(args)
    responses_model = None
    if args.api == "responses":
        responses_payload_data, responses_model = responses_payload(args, model)
        data, provider, endpoint, transport, request_url, previous_errors = request_responses_with_retry(
            responses_payload_data,
            args.timeout,
            max_attempts=getattr(args, "max_attempts", PRIMARY_EXTRA_RETRY_ATTEMPTS + 1),
        )
        api_channel = "configured_provider_responses"
    else:
        data, provider, endpoint, transport, request_url, previous_errors = request_with_retry(
            "generate",
            payload,
            args.timeout,
            max_attempts=getattr(args, "max_attempts", PRIMARY_EXTRA_RETRY_ATTEMPTS + 1),
        )
        api_channel = cli_channel_label(provider)
    items = response_image_items(data)
    if not items:
        raise SystemExit(
            no_image_items_error(
                provider=provider,
                endpoint=endpoint,
                transport=transport,
                request_url=request_url,
                data=data,
            )
        )
    out_dir = Path(args.out_dir) if args.out_dir else output_dir()
    paths = [save_image_from_item(item, out_dir, args.filename, index, provider) for index, item in enumerate(items)]
    size_check = validate_output_sizes(
        paths,
        args.size,
        require_exact=exact_size_is_required(args.size, getattr(args, "require_exact_size", False)),
    )
    result = {
        "ok": not size_check["size_validation_failed"],
        "operation": "generate",
        "attempt_count": len(previous_errors) + 1,
        **image_model_selection(args),
        "skill_primary_channel": "cm_image_gen_cli",
        "execution_channel": "cm_image_gen_cli",
        "api_channel": api_channel,
        "api_provider": cli_provider_label(provider),
        "request_url": request_url,
        "provider": provider.name,
        "base_url": provider.base_url,
        "endpoint": endpoint,
        "transport": transport,
        "model": model,
        "paths": [str(path.resolve()) for path in paths],
        "usage": data.get("usage"),
        "created": data.get("created"),
        **size_check,
    }
    if size_check["size_validation_failed"]:
        result["error_kind"] = "image_size_mismatch"
    if responses_model:
        result["responses_model"] = responses_model
        result["responses_reasoning"] = getattr(args, "responses_reasoning", None)
        result["image_tool_model"] = model
    if data.get("_cm_sse_parsed"):
        result["parsed_sse_stream"] = True
        result["sse_diagnostics"] = data.get("_cm_sse_diagnostics")
    if data.get("_cm_partial_response_salvaged"):
        result["partial_response_salvaged"] = True
        result["partial_response_diagnostics"] = data.get("_cm_partial_response_diagnostics")
    if data.get("_cm_async_poll_used"):
        result["async_poll_used"] = True
        result["async_poll_diagnostics"] = data.get("_cm_async_poll_diagnostics")
    if previous_errors:
        result["previous_errors"] = previous_errors
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def edit(args: argparse.Namespace) -> int:
    image_paths = [Path(value).expanduser() for value in args.image]
    input_images = [load_input_image(image_path, "Input image") for image_path in image_paths]
    mask_path = Path(args.mask).expanduser() if args.mask else None
    mask_image = load_input_image(mask_path, "Mask image") if mask_path else None
    payload, model = image_payload(args)
    multipart_fields = {
        "model": model,
        "prompt": args.prompt,
        "size": args.size,
        "response_format": args.response_format,
        "n": args.n,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
    }
    multipart_files = [{"field": "image", "image": image} for image in input_images]
    if mask_image:
        multipart_files.append({"field": "mask", "image": mask_image})
    responses_model = None
    if args.api == "responses":
        response_images = input_images + ([mask_image] if mask_image else [])
        responses_payload_data, responses_model = responses_payload(args, model, response_images)
        data, provider, endpoint, transport, request_url, previous_errors = request_responses_with_retry(
            responses_payload_data,
            args.timeout,
            max_attempts=getattr(args, "max_attempts", PRIMARY_EXTRA_RETRY_ATTEMPTS + 1),
        )
        api_channel = "configured_provider_responses"
    else:
        data, provider, endpoint, transport, request_url, previous_errors = request_with_retry(
            "edit",
            payload,
            args.timeout,
            {"fields": multipart_fields, "files": multipart_files},
            max_attempts=getattr(args, "max_attempts", PRIMARY_EXTRA_RETRY_ATTEMPTS + 1),
        )
        api_channel = cli_channel_label(provider)
    items = response_image_items(data)
    if not items:
        raise SystemExit(
            no_image_items_error(
                provider=provider,
                endpoint=endpoint,
                transport=transport,
                request_url=request_url,
                data=data,
            )
        )
    out_dir = Path(args.out_dir) if args.out_dir else output_dir()
    paths = [save_image_from_item(item, out_dir, args.filename, index, provider) for index, item in enumerate(items)]
    size_check = validate_output_sizes(
        paths,
        args.size,
        require_exact=exact_size_is_required(args.size, getattr(args, "require_exact_size", False)),
    )
    result = {
        "ok": not size_check["size_validation_failed"],
        "operation": "edit",
        "attempt_count": len(previous_errors) + 1,
        **image_model_selection(args),
        "skill_primary_channel": "cm_image_gen_cli",
        "execution_channel": "cm_image_gen_cli",
        "api_channel": api_channel,
        "api_provider": cli_provider_label(provider),
        "request_url": request_url,
        "provider": provider.name,
        "base_url": provider.base_url,
        "endpoint": endpoint,
        "transport": transport,
        "model": model,
        "source_images": [str(image.path) for image in input_images],
        "paths": [str(path.resolve()) for path in paths],
        "usage": data.get("usage"),
        "created": data.get("created"),
        **size_check,
    }
    if size_check["size_validation_failed"]:
        result["error_kind"] = "image_size_mismatch"
    if responses_model:
        result["responses_model"] = responses_model
        result["responses_reasoning"] = getattr(args, "responses_reasoning", None)
        result["image_tool_model"] = model
    if data.get("_cm_sse_parsed"):
        result["parsed_sse_stream"] = True
        result["sse_diagnostics"] = data.get("_cm_sse_diagnostics")
    if data.get("_cm_partial_response_salvaged"):
        result["partial_response_salvaged"] = True
        result["partial_response_diagnostics"] = data.get("_cm_partial_response_diagnostics")
    if data.get("_cm_async_poll_used"):
        result["async_poll_used"] = True
        result["async_poll_diagnostics"] = data.get("_cm_async_poll_diagnostics")
    if previous_errors:
        result["previous_errors"] = previous_errors
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and edit images through the configured Sub2API/OpenAI-compatible provider.")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--prompt", required=True)
    gen.add_argument(
        "--api",
        choices=["images", "responses"],
        default="responses",
        help="HTTP API route to use. Default: Responses API with the image_generation tool.",
    )
    gen.add_argument("--model")
    gen.add_argument("--responses-model")
    gen.add_argument("--tools")
    gen.add_argument("--instructions")
    gen.add_argument("--responses-extra")
    gen.add_argument("--size", default=DEFAULT_SIZE)
    gen.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["b64_json", "url"])
    gen.add_argument("--out-dir")
    gen.add_argument("--filename")
    gen.add_argument("--n", type=int)
    gen.add_argument("--quality")
    gen.add_argument("--background")
    gen.add_argument("--output-format", choices=["png", "jpeg", "webp"])
    gen.add_argument(
        "--require-exact-size", action="store_true",
        help="Fail when decoded output dimensions do not equal --size (4K requests are strict automatically).",
    )
    gen.add_argument("--timeout", type=int, default=600)
    gen.add_argument("--max-attempts", type=retry_attempt_count, default=PRIMARY_EXTRA_RETRY_ATTEMPTS + 1,
                     help="Maximum image submissions, including the first (1-5; default 3).")
    gen.set_defaults(func=generate)
    edit_parser = sub.add_parser("edit")
    edit_parser.add_argument("--prompt", required=True)
    edit_parser.add_argument("--image", action="append", required=True)
    edit_parser.add_argument("--mask")
    edit_parser.add_argument(
        "--api",
        choices=["images", "responses"],
        default="responses",
        help="HTTP API route to use. Default: Responses API with image inputs and the image_generation tool.",
    )
    edit_parser.add_argument("--model")
    edit_parser.add_argument("--responses-model")
    edit_parser.add_argument("--tools")
    edit_parser.add_argument("--instructions")
    edit_parser.add_argument("--responses-extra")
    edit_parser.add_argument("--size", default=DEFAULT_SIZE)
    edit_parser.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["b64_json", "url"])
    edit_parser.add_argument("--out-dir")
    edit_parser.add_argument("--filename")
    edit_parser.add_argument("--n", type=int)
    edit_parser.add_argument("--quality")
    edit_parser.add_argument("--background")
    edit_parser.add_argument("--output-format", choices=["png", "jpeg", "webp"])
    edit_parser.add_argument(
        "--require-exact-size", action="store_true",
        help="Fail when decoded output dimensions do not equal --size (4K requests are strict automatically).",
    )
    edit_parser.add_argument("--timeout", type=int, default=600)
    edit_parser.add_argument("--max-attempts", type=retry_attempt_count, default=PRIMARY_EXTRA_RETRY_ATTEMPTS + 1,
                             help="Maximum image submissions, including the first (1-5; default 3).")
    edit_parser.set_defaults(func=edit)
    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--api", choices=["images", "responses"], default="responses")
    doctor_parser.add_argument("--operation", choices=["generate", "edit", "all"], default="all")
    doctor_parser.add_argument("--model")
    doctor_parser.add_argument("--responses-model")
    doctor_parser.add_argument("--size", default=DEFAULT_SIZE)
    doctor_parser.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["b64_json", "url"])
    doctor_parser.add_argument("--n", type=int)
    doctor_parser.add_argument("--quality")
    doctor_parser.add_argument("--background")
    doctor_parser.add_argument("--output-format", choices=["png", "jpeg", "webp"])
    doctor_parser.add_argument("--show-payload-shape", action="store_true")
    doctor_parser.set_defaults(func=doctor)
    check_parser = sub.add_parser("check-config")
    check_parser.add_argument("--api", choices=["images", "responses"], default="responses")
    check_parser.add_argument("--operation", choices=["generate", "edit", "all"], default="all")
    check_parser.add_argument("--model")
    check_parser.add_argument("--responses-model")
    check_parser.add_argument("--size", default=DEFAULT_SIZE)
    check_parser.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["b64_json", "url"])
    check_parser.add_argument("--n", type=int)
    check_parser.add_argument("--quality")
    check_parser.add_argument("--background")
    check_parser.add_argument("--output-format", choices=["png", "jpeg", "webp"])
    check_parser.add_argument("--show-payload-shape", action="store_true")
    check_parser.set_defaults(func=doctor)
    probe_parser = sub.add_parser("transport-probe")
    probe_parser.add_argument("--operation", choices=["generate", "edit"], required=True)
    probe_parser.add_argument("--client", choices=["urllib", "requests", "both"], default="both")
    probe_parser.add_argument("--prompt", required=True)
    probe_parser.add_argument("--image", action="append")
    probe_parser.add_argument("--mask")
    probe_parser.add_argument("--model")
    probe_parser.add_argument("--size", default=DEFAULT_SIZE)
    probe_parser.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["b64_json", "url"])
    probe_parser.add_argument("--out-dir")
    probe_parser.add_argument("--filename")
    probe_parser.add_argument("--n", type=int)
    probe_parser.add_argument("--quality")
    probe_parser.add_argument("--background")
    probe_parser.add_argument("--output-format", choices=["png", "jpeg", "webp"])
    probe_parser.add_argument("--timeout", type=int, default=600)
    probe_parser.add_argument("--save-images", action="store_true")
    probe_parser.set_defaults(func=transport_probe)
    for command_parser in (gen, edit_parser, doctor_parser, check_parser, probe_parser):
        command_parser.add_argument(
            "--check-model", action="store_true",
            help="Read GET /models and require the image model to be listed before sending an image request.",
        )
    for command_parser in (gen, edit_parser, doctor_parser, check_parser):
        command_parser.add_argument("--responses-reasoning", choices=["low", "medium", "high", "xhigh", "max", "ultra"])
        command_parser.set_defaults(**controller_defaults())
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
