#!/usr/bin/env python3
"""Safe MiniMax-H3 video generation helper.

The CLI deliberately separates preview from submission. It uses only the
Python standard library so it can run from a personal Codex skill directory.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


if hasattr(sys.stdout, "reconfigure"):
    # Codex captures subprocess output as UTF-8 even when Windows Python
    # inherits a legacy GBK console encoding.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_BASE_URL = "https://metaso.cn/api/minimax"
DEFAULT_API_KEY_ENV = "METASO_MINIMAX_API_KEY"
DEFAULT_MODEL = "MiniMax-H3"
DEFAULT_RESOLUTION = "768P"
DEFAULT_RATIO = "9:16"
DEFAULT_DURATION = 4
MAX_BODY_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_AUDIO_BYTES = 15 * 1024 * 1024
DEFAULT_TAIL_SCALE = 2.0
DEFAULT_SHARPEN_RADIUS = 0.8
DEFAULT_SHARPEN_PERCENT = 35
DEFAULT_SHARPEN_THRESHOLD = 3
STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
RATIOS = {"adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
MEDIA_TYPES = {
    "image": ("image_url", MAX_IMAGE_BYTES),
    "video": ("video_url", MAX_VIDEO_BYTES),
    "audio": ("audio_url", MAX_AUDIO_BYTES),
}
PROJECT_CHARACTER_REFERENCES = {
    "programmer": Path("我的表述/00_人物设定/参考图/程序员_参考.png"),
    "boss": Path("我的表述/00_人物设定/参考图/老板_参考.png"),
    "hr": Path("我的表述/00_人物设定/参考图/女性HR_参考.png"),
}


class CliError(RuntimeError):
    """An expected, user-actionable CLI error."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aspect_ratio_label(width: int, height: int) -> str:
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError(f"找不到 JSON 文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CliError(f"JSON 无法解析：{path}（{exc}）") from exc


def normalize_base_url(value: str | None) -> str:
    value = (value or DEFAULT_BASE_URL).strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise CliError(f"base URL 必须以 http:// 或 https:// 开头：{value}")
    return value


def endpoint(base_url: str, suffix: str) -> str:
    return f"{normalize_base_url(base_url)}/{suffix.lstrip('/')}"


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "mm_file://", "data:"))


def data_uri_mime(value: str) -> str | None:
    if not value.startswith("data:"):
        return None
    match = re.match(r"^data:([^;,]+)", value, flags=re.IGNORECASE)
    return match.group(1).lower() if match else None


def guess_mime(path: Path, kind: str) -> str:
    known = {
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".mov": "video/quicktime",
        ".mp4": "video/mp4",
    }
    mime = known.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
    if not mime:
        mime = {"image": "image/png", "video": "video/mp4", "audio": "audio/mpeg"}[kind]
    return mime


def source_from_value(value: str, kind: str) -> dict[str, Any]:
    """Create a preview-safe source descriptor without embedding local bytes."""
    value = value.strip()
    if not value:
        raise CliError(f"{kind} 参考素材不能为空")
    if is_url(value):
        mime = data_uri_mime(value)
        if value.startswith("data:") and len(value.encode("utf-8")) > MAX_BODY_BYTES:
            raise CliError("data URI 已超过 64 MB 请求体上限；请使用公网 URL 或 mm_file://。")
        return {"kind": "data_uri" if value.startswith("data:") else "url", "url": value, **({"mime_type": mime} if mime else {})}

    path = Path(value).expanduser()
    if not path.is_file():
        raise CliError(f"找不到本地参考素材：{path}")
    path = path.resolve()
    stat = path.stat()
    mime = guess_mime(path, kind)
    if not mime.startswith(f"{kind}/"):
        raise CliError(f"{path} 看起来不是 {kind} 文件（检测到 MIME：{mime}）")
    limit = MEDIA_TYPES[kind][1]
    if stat.st_size > limit:
        raise CliError(f"{path} 为 {stat.st_size} bytes，超过 {kind} 单文件上限 {limit} bytes；请使用公网 URL 或 mm_file://。")
    return {
        "kind": "local_file",
        "path": str(path),
        "mime_type": mime,
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def source_label(source: dict[str, Any]) -> str:
    kind = source.get("kind")
    if kind == "local_file":
        return f"本地文件 {source['path']} | {source['size_bytes']} bytes | sha256={source['sha256']}"
    if kind == "data_uri":
        return f"data URI | {source.get('mime_type', 'unknown')} | 不展示内容"
    return str(source.get("url", ""))


def media_item(kind: str, source: dict[str, Any], role: str, character_id: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"type": MEDIA_TYPES[kind][0], "role": role, "source": source}
    if character_id:
        item["character_id"] = character_id
    return item


def discover_project_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()
    current = Path.cwd().resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "我的表述").is_dir() and (candidate / ".git").exists():
            return candidate
    return current


def parse_character_reference(value: str) -> tuple[str, str]:
    raw = value.strip()
    if not raw:
        raise CliError("人物参考图不能为空")
    if "=" in raw:
        character_id, source = raw.split("=", 1)
        character_id = character_id.strip()
        source = source.strip()
        if not character_id or not source:
            raise CliError("人物参考图格式应为 character_id=路径，例如 programmer=E:\\path\\程序员_参考.png")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", character_id):
            raise CliError(f"人物参考 id 只能包含字母、数字、下划线和连字符：{character_id}")
        return character_id, source
    return Path(raw).stem, raw


def project_character_reference(project_root: Path, character_id: str) -> tuple[str, str]:
    relative_path = PROJECT_CHARACTER_REFERENCES.get(character_id)
    if not relative_path:
        allowed = ", ".join(sorted(PROJECT_CHARACTER_REFERENCES))
        raise CliError(f"未知人物 id：{character_id}；可用值：{allowed}。自定义图片请使用 --character-reference id=路径。")
    path = (project_root / relative_path).resolve()
    if not path.is_file():
        raise CliError(f"人物 {character_id} 的项目参考图不存在：{path}")
    return character_id, str(path)


def source_identity(source: dict[str, Any]) -> tuple[str, str]:
    if source.get("kind") == "local_file":
        return "local_file", str(Path(str(source["path"])).resolve()).casefold()
    return str(source.get("kind", "")), str(source.get("url", ""))


def normalize_content_json(path: Path) -> list[dict[str, Any]]:
    raw = read_json(path)
    if not isinstance(raw, list):
        raise CliError("--content-json 必须是 content 数组")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise CliError(f"content[{index}] 必须是带 type 的对象")
        item_type = item["type"]
        if item_type == "text":
            normalized.append({"type": "text", "text": str(item.get("text", ""))})
            continue
        kind = {"image_url": "image", "video_url": "video", "audio_url": "audio"}.get(item_type)
        if not kind:
            raise CliError(f"content[{index}] 的 type 不支持：{item_type}")
        container = item.get(item_type)
        if not isinstance(container, dict) or not isinstance(container.get("url"), str):
            raise CliError(f"content[{index}] 缺少 {item_type}.url")
        role = item.get("role") or {"image": "reference_image", "video": "reference_video", "audio": "reference_audio"}[kind]
        normalized.append(media_item(kind, source_from_value(container["url"], kind), role, str(item.get("character_id") or "") or None))
    return normalized


def build_content(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.content_json:
        if any([args.prompt, args.prompt_file, args.reference_image, args.reference_video, args.reference_audio, args.character, args.character_reference, args.first_frame, args.last_frame]):
            raise CliError("--content-json 不能和 prompt 或参考素材参数混用")
        return normalize_content_json(Path(args.content_json).expanduser().resolve())

    if args.prompt is not None and args.prompt_file:
        raise CliError("--prompt 和 --prompt-file 只能选一个")
    if args.prompt_file:
        prompt_path = Path(args.prompt_file).expanduser()
        if not prompt_path.is_file():
            raise CliError(f"找不到提示词文件：{prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8")
    else:
        prompt = args.prompt or ""
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if args.first_frame and args.last_frame:
        content.append(media_item("image", source_from_value(args.first_frame, "image"), "first_frame"))
        content.append(media_item("image", source_from_value(args.last_frame, "image"), "last_frame"))
    elif args.first_frame:
        content.append(media_item("image", source_from_value(args.first_frame, "image"), "first_frame"))
    elif args.last_frame:
        content.append(media_item("image", source_from_value(args.last_frame, "image"), "last_frame"))

    reference_keys: set[tuple[str, str]] = set()

    def append_image_reference(value: str, character_id: str | None = None) -> None:
        source = source_from_value(value, "image")
        key = source_identity(source)
        if key in reference_keys:
            return
        reference_keys.add(key)
        content.append(media_item("image", source, "reference_image", character_id))

    # Keep explicit reference images first. In R2VA prompts, callers can use
    # the first reference image as a soft start/composition anchor, followed
    # by character identity images supplied through --character.
    for value in args.reference_image or []:
        append_image_reference(value)
    project_root = discover_project_root(args.project_root)
    for character_id in args.character or []:
        resolved_id, path = project_character_reference(project_root, character_id)
        append_image_reference(path, resolved_id)
    for character_spec in args.character_reference or []:
        character_id, value = parse_character_reference(character_spec)
        append_image_reference(value, character_id)
    for value in args.reference_video or []:
        content.append(media_item("video", source_from_value(value, "video"), "reference_video"))
    for value in args.reference_audio or []:
        content.append(media_item("audio", source_from_value(value, "audio"), "reference_audio"))
    return content


def validate_request(request: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if request.get("model") != DEFAULT_MODEL:
        errors.append(f"当前脚本只允许 model={DEFAULT_MODEL}")
    if request.get("resolution") not in {"768P", "2K"}:
        errors.append("resolution 必须是 768P 或 2K")
    duration = request.get("duration")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 4 <= duration <= 15:
        errors.append("duration 必须是 4–15 的整数")
    if request.get("ratio") not in RATIOS:
        errors.append(f"ratio 必须是 {', '.join(sorted(RATIOS))}")
    content = request.get("content")
    if not isinstance(content, list):
        errors.append("content 必须是数组")
        content = []
    text_items = [item for item in content if isinstance(item, dict) and item.get("type") == "text"]
    if len(text_items) != 1 or not str(text_items[0].get("text", "")).strip():
        errors.append("content 必须包含且只能包含一个非空 text")
    elif len(str(text_items[0].get("text", ""))) > 7000:
        errors.append("text 最多 7000 个字符")

    roles: list[str] = []
    local_body_estimate = 0
    media_counts = {"image_url": 0, "video_url": 0, "audio_url": 0}
    for index, item in enumerate(content):
        if not isinstance(item, dict):
            errors.append(f"content[{index}] 不是对象")
            continue
        item_type = item.get("type")
        if item_type == "text":
            continue
        if item_type not in media_counts:
            errors.append(f"content[{index}] type 不支持：{item_type}")
            continue
        media_counts[item_type] += 1
        role = item.get("role")
        roles.append(role)
        source = item.get("source")
        if not isinstance(source, dict):
            errors.append(f"content[{index}] 缺少 source")
            continue
        if source.get("kind") == "local_file":
            size = int(source.get("size_bytes", 0))
            local_body_estimate += 4 * math.ceil(size / 3) + len(str(source.get("mime_type", "application/octet-stream"))) + 32
        if role in {"first_frame", "last_frame"} and item_type != "image_url":
            errors.append(f"content[{index}] 的 {role} 必须是 image_url")
        if role not in {"first_frame", "last_frame", "reference_image", "reference_video", "reference_audio"}:
            errors.append(f"content[{index}] role 不支持：{role}")
        if item.get("character_id") and (item_type != "image_url" or role != "reference_image"):
            errors.append(f"content[{index}] 的 character_id 只能标注 reference_image")

    first_last = {role for role in roles if role in {"first_frame", "last_frame"}}
    reference_roles = {role for role in roles if isinstance(role, str) and role.startswith("reference_")}
    if first_last and reference_roles:
        errors.append("MiniMax-H3 不允许硬首/尾帧与人物 reference_image（或其他 reference_*）混用；要保证上一段尾帧，请去掉 --character/--character-reference 并使用 first-frame；要上传人物参考图，请去掉 first-frame/last-frame，改用 reference-image 模式。")
    if not (first_last and reference_roles) and "first_frame" in first_last and media_counts["image_url"] > 1 and "last_frame" not in first_last:
        errors.append("first_frame 模式最多一张首帧图片")
    if not (first_last and reference_roles) and "last_frame" in first_last and media_counts["image_url"] > 1 and "first_frame" not in first_last:
        errors.append("last_frame 模式最多一张尾帧图片")
    if media_counts["image_url"] > 9:
        errors.append("参考图片最多 9 张")
    if media_counts["video_url"] > 3:
        errors.append("参考视频最多 3 个")
    if media_counts["audio_url"] > 3:
        errors.append("参考音频最多 3 个")

    if first_last:
        mode = "i2va"
        if request.get("ratio") != "adaptive":
            warnings.append("首尾帧图生视频的实际比例由输入图片决定；ratio=9:16 会被接口忽略，输入图片本身应为竖屏。")
    elif reference_roles:
        mode = "r2va"
        if any(item.get("character_id") for item in content if isinstance(item, dict)):
            warnings.append("人物参考图将作为 reference_image 实际上传；只上传当前段落可见或需要生成身份的角色，不要上传未出场的 HR。")
    else:
        mode = "t2va"
        if request.get("ratio") == "adaptive":
            errors.append("文生视频不能使用 ratio=adaptive，请指定 9:16 等具体比例")
    if local_body_estimate > MAX_BODY_BYTES:
        errors.append("本地文件转换为 data URI 后估算会超过 64 MB 请求体上限；请改用公网 URL 或 mm_file://。")
    if any(item.get("source", {}).get("kind") == "local_file" for item in content if isinstance(item, dict) and isinstance(item.get("source"), dict)):
        warnings.append("本地素材将在提交时转换为 data URI；提交前会重新校验文件 SHA-256，预览不包含二进制内容。")
    if duration == 4:
        warnings.append("当前是 4 秒测试时长；如用于正式 15 秒段，请重新预览并显式设置 duration。")
    if errors:
        raise CliError("请求校验失败：\n- " + "\n- ".join(errors))
    return mode, warnings


def preview_from_args(args: argparse.Namespace) -> dict[str, Any]:
    content = build_content(args)
    request = {
        "model": args.model,
        "content": content,
        "resolution": args.resolution,
        "duration": args.duration,
        "ratio": args.ratio,
    }
    if args.aigc_watermark:
        request["aigc_watermark"] = True
    mode, warnings = validate_request(request)
    base_url = normalize_base_url(args.base_url or os.environ.get("METASO_MINIMAX_BASE_URL"))
    query_base = normalize_base_url(args.query_base_url or os.environ.get("METASO_MINIMAX_QUERY_BASE_URL") or base_url)
    return {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "segment_id": args.segment_id,
        "mode": mode,
        "api": {
            "create_endpoint": endpoint(base_url, "/v2/video_generation"),
            "query_endpoint_template": endpoint(query_base, "/v2/query/video_generation/{task_id}"),
            "api_key_env": args.api_key_env,
        },
        "request": request,
        "warnings": warnings,
    }


def print_preview(preview: dict[str, Any], path: Path) -> str:
    digest = sha256_bytes(path.read_bytes())
    request = preview["request"]
    print("预览已生成：尚未联网，也未读取 API key。")
    print(f"预览文件：{path.resolve()}")
    print(f"preview_sha256：{digest}")
    print(f"模式：{preview['mode']} | 模型：{request['model']} | 分辨率：{request['resolution']} | 比例：{request['ratio']} | 时长：{request['duration']} 秒")
    print(f"创建接口：{preview['api']['create_endpoint']}")
    print(f"查询接口：{preview['api']['query_endpoint_template']}")
    text_items = [item for item in request["content"] if item["type"] == "text"]
    print("\n最终提示词：\n" + text_items[0]["text"])
    print("\n参考素材：")
    for index, item in enumerate(request["content"]):
        if item["type"] == "text":
            continue
        character_label = f" | character_id={item['character_id']}" if item.get("character_id") else ""
        print(f"  [{index}] {item['role']}{character_label}：{source_label(item['source'])}")
    if preview.get("warnings"):
        print("\n警告：")
        for warning in preview["warnings"]:
            print(f"  - {warning}")
    print("\n只有用户明确确认这份预览后，才能使用 --confirm + --confirm-sha256 提交。")
    return digest


def resolve_source(source: dict[str, Any]) -> str:
    kind = source.get("kind")
    if kind in {"url", "data_uri"}:
        return str(source["url"])
    if kind != "local_file":
        raise CliError(f"未知 source.kind：{kind}")
    path = Path(source["path"])
    if not path.is_file():
        raise CliError(f"提交时找不到本地素材：{path}")
    expected = source.get("sha256")
    actual = sha256_file(path)
    if expected and actual.lower() != str(expected).lower():
        raise CliError(f"本地素材在预览后发生变化：{path}（预览 {expected}，当前 {actual}）；请重新 prepare。")
    raw = path.read_bytes()
    mime = source.get("mime_type") or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def build_api_payload(preview: dict[str, Any]) -> dict[str, Any]:
    request = preview["request"]
    payload: dict[str, Any] = {key: value for key, value in request.items() if key != "content"}
    content: list[dict[str, Any]] = []
    for item in request["content"]:
        if item["type"] == "text":
            content.append({"type": "text", "text": item["text"]})
            continue
        item_type = item["type"]
        content_item: dict[str, Any] = {"type": item_type, item_type: {"url": resolve_source(item["source"])}}
        if item.get("role"):
            content_item["role"] = item["role"]
        content.append(content_item)
    payload["content"] = content
    return payload


def summarize_payload(preview: dict[str, Any]) -> dict[str, Any]:
    """Return the request shape without local data URI bytes."""
    return {
        "model": preview["request"]["model"],
        "content": [
            {"type": "text", "text": item["text"]}
            if item["type"] == "text"
            else {
                "type": item["type"],
                "role": item.get("role"),
                **({"character_id": item["character_id"]} if item.get("character_id") else {}),
                "source": item["source"],
            }
            for item in preview["request"]["content"]
        ],
        **{key: value for key, value in preview["request"].items() if key not in {"model", "content"}},
    }


def auth_key(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        raise CliError(f"未找到环境变量 {env_name}；请在本机安全设置，不要把 key 写进命令行或文件。")
    return value


def redact(value: Any, secret: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: ("<redacted>" if key.lower() in {"authorization", "api_key", "apikey", "token", "secret"} else redact(item, secret)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, str):
        if secret:
            value = value.replace(secret, "<redacted>")
        return re.sub(r"(?i)(bearer\s+)[^\s,}\]]+", r"\1<redacted>", value)
    return value


def response_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    body = canonical_bytes(payload) if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read()
        try:
            detail: Any = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            detail = raw.decode("utf-8", errors="replace")
        raise CliError(f"API HTTP {exc.code}：{json.dumps(redact(detail, api_key), ensure_ascii=False)}") from exc
    except URLError as exc:
        raise CliError(f"API 网络请求失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise CliError("API 请求超时") from exc
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"API 返回不是 JSON：{raw[:300]!r}") from exc
    if not isinstance(parsed, dict):
        raise CliError("API 返回 JSON 顶层不是对象")
    return parsed


def task_id_from_response(response: dict[str, Any]) -> str:
    task_id = response.get("task_id")
    if not task_id and isinstance(response.get("task"), dict):
        task_id = response["task"].get("id")
    if not task_id:
        raise CliError(f"创建响应没有 task_id：{json.dumps(redact(response), ensure_ascii=False)}")
    return str(task_id)


def task_from_response(response: dict[str, Any]) -> dict[str, Any]:
    task = response.get("task")
    if isinstance(task, dict):
        return task
    if isinstance(response, dict) and isinstance(response.get("status"), str):
        return response
    raise CliError(f"查询响应没有 task 对象：{json.dumps(redact(response), ensure_ascii=False)}")


def record_path_for(record_dir: Path, task_id: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", task_id)
    return record_dir / f"task-{safe}.json"


def submit_preview(preview_path: Path, confirm: bool, confirm_sha256: str, record_dir: Path) -> tuple[Path, dict[str, Any]]:
    if not confirm:
        raise CliError("提交被阻止：必须显式传 --confirm。")
    if not preview_path.is_file():
        raise CliError(f"找不到预览文件：{preview_path}")
    preview_bytes = preview_path.read_bytes()
    actual_hash = sha256_bytes(preview_bytes)
    if actual_hash.lower() != confirm_sha256.lower():
        raise CliError(f"确认 hash 不匹配：文件当前为 {actual_hash}；请重新审阅并使用最新 preview_sha256。")
    preview = read_json(preview_path)
    if not isinstance(preview, dict) or preview.get("schema_version") != 1:
        raise CliError("不是受支持的预览文件（schema_version 必须为 1）")
    if not isinstance(preview.get("request"), dict) or not isinstance(preview.get("api"), dict):
        raise CliError("预览文件缺少 request 或 api 对象")
    validate_request(preview["request"])
    api_key_env = str(preview["api"].get("api_key_env") or DEFAULT_API_KEY_ENV)
    api_key = auth_key(api_key_env)
    create_url = str(preview["api"]["create_endpoint"])
    payload = build_api_payload(preview)
    response = response_json("POST", create_url, api_key, payload)
    task_id = task_id_from_response(response)
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_path_for(record_dir, task_id)
    record = {
        "schema_version": 1,
        "task_id": task_id,
        "status": "submitted",
        "segment_id": preview.get("segment_id"),
        "preview_path": str(preview_path.resolve()),
        "preview_sha256": actual_hash,
        "api": {
            "create_endpoint": create_url,
            "query_endpoint_template": preview["api"]["query_endpoint_template"],
            "api_key_env": api_key_env,
        },
        "request": summarize_payload(preview),
        "submitted_response": redact(response, api_key),
        "latest_response": redact(response, api_key),
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
    }
    write_json(record_path, record)
    print(f"已提交任务：task_id={task_id}")
    print(f"任务记录：{record_path.resolve()}")
    return record_path, record


def extract_tail_frame(video_path: Path, output_path: Path, overwrite: bool = False) -> dict[str, Any]:
    if not video_path.is_file():
        raise CliError(f"找不到视频：{video_path}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise CliError("提取尾帧需要 ffmpeg；视频已可先保留，安装 ffmpeg 后重试 extract-tail。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        raise CliError(f"尾帧已存在（如需覆盖请传 --overwrite）：{output_path}")
    last_error = ""
    for offset in ("-0.05", "-0.5"):
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-sseof", offset, "-i", str(video_path), "-frames:v", "1", str(output_path)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0:
            break
        last_error = completed.stderr.strip()
    else:
        raise CliError(f"ffmpeg 尾帧提取失败：{last_error}")
    info: dict[str, Any] = {
        "source_video": str(video_path.resolve()),
        "tail_frame": str(output_path.resolve()),
        "sha256": sha256_file(output_path),
        "created_at_utc": utc_now(),
    }
    # Keep dimensions in the key-free manifest without making Pillow a
    # prerequisite for plain ffmpeg tail extraction. The normal output is PNG;
    # this reads only its fixed-size IHDR header as a standard-library fallback.
    if output_path.suffix.lower() == ".png":
        with output_path.open("rb") as handle:
            header = handle.read(24)
        if len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
            info["width"], info["height"] = struct.unpack(">II", header[16:24])
            info["aspect_ratio"] = aspect_ratio_label(info["width"], info["height"])
    return info


def enhance_tail_frame(
    input_path: Path,
    output_path: Path,
    scale: float = DEFAULT_TAIL_SCALE,
    overwrite: bool = False,
    sharpen_radius: float = DEFAULT_SHARPEN_RADIUS,
    sharpen_percent: int = DEFAULT_SHARPEN_PERCENT,
    sharpen_threshold: int = DEFAULT_SHARPEN_THRESHOLD,
) -> dict[str, Any]:
    """Create a deterministic, lightly sharpened enlarged copy of a tail frame.

    This deliberately uses interpolation and a restrained unsharp mask rather
    than generative restoration. It makes the existing edges easier to inspect
    while keeping the original frame untouched and avoiding invented facial
    detail.
    """
    if not input_path.is_file():
        raise CliError(f"找不到尾帧图片：{input_path}")
    if input_path.resolve() == output_path.resolve():
        raise CliError("增强输出必须是新文件，不能覆盖原始尾帧")
    if not math.isfinite(scale) or not 1.0 <= scale <= 4.0:
        raise CliError("尾帧增强 scale 必须在 1.0–4.0 之间")
    if not math.isfinite(sharpen_radius) or not 0.0 <= sharpen_radius <= 3.0:
        raise CliError("尾帧增强 sharpen_radius 必须在 0–3 之间")
    if not 0 <= sharpen_percent <= 150:
        raise CliError("尾帧增强 sharpen_percent 必须在 0–150 之间")
    if not 0 <= sharpen_threshold <= 20:
        raise CliError("尾帧增强 sharpen_threshold 必须在 0–20 之间")
    if output_path.exists() and not overwrite:
        raise CliError(f"增强尾帧已存在（如需覆盖请传 --overwrite）：{output_path}")
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:
        raise CliError("尾帧增强需要 Pillow；请先安装 Pillow（python -m pip install Pillow）") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".part")
    if temp_path.exists():
        temp_path.unlink()
    try:
        with Image.open(input_path) as source:
            source = ImageOps.exif_transpose(source)
            source_width, source_height = source.size
            width = max(1, round(source_width * scale))
            height = max(1, round(source_height * scale))
            resampling = getattr(Image, "Resampling", Image).LANCZOS
            enhanced = source.resize((width, height), resample=resampling)
            enhanced = enhanced.filter(
                ImageFilter.UnsharpMask(
                    radius=sharpen_radius,
                    percent=sharpen_percent,
                    threshold=sharpen_threshold,
                )
            )
            enhanced.save(temp_path, format="PNG")
    except CliError:
        raise
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise CliError(f"尾帧增强失败：{input_path}（{exc}）") from exc
    if output_path.exists() and overwrite:
        output_path.unlink()
    temp_path.replace(output_path)
    return {
        "source_frame": str(input_path.resolve()),
        "source_sha256": sha256_file(input_path),
        "source_width": source_width,
        "source_height": source_height,
        "source_aspect_ratio": aspect_ratio_label(source_width, source_height),
        "enhanced_frame": str(output_path.resolve()),
        "enhanced_sha256": sha256_file(output_path),
        "enhanced_width": width,
        "enhanced_height": height,
        "enhanced_aspect_ratio": aspect_ratio_label(width, height),
        "scale": scale,
        "method": "Pillow Lanczos resize + light UnsharpMask; non-generative",
        "sharpen": {
            "radius": sharpen_radius,
            "percent": sharpen_percent,
            "threshold": sharpen_threshold,
        },
        "created_at_utc": utc_now(),
    }


def tail_scale_label(scale: float) -> str:
    return f"{scale:g}x"


def ffprobe_video(video_path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"available": False}
    command = [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_name", "-of", "json", str(video_path)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        return {"available": False, "error": completed.stderr.strip()}
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"available": False, "error": "ffprobe returned invalid JSON"}
    return {"available": True, "ffprobe": data}


def response_video_url(record: dict[str, Any]) -> str:
    latest = record.get("latest_response", {})
    task = latest.get("task", latest) if isinstance(latest, dict) else {}
    content = task.get("content", {}) if isinstance(task, dict) else {}
    url = content.get("url") if isinstance(content, dict) else None
    if not url:
        raise CliError("任务记录中没有成功视频 URL；先对该 task 运行 poll，或用 --video-url 指定 URL。")
    return str(url)


def download_url(url: str, output_path: Path, overwrite: bool = False) -> str:
    if output_path.exists() and not overwrite:
        raise CliError(f"视频已存在（如需覆盖请传 --overwrite）：{output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".part")
    if temp_path.exists():
        temp_path.unlink()
    digest = hashlib.sha256()
    try:
        with urlopen(Request(url, headers={"Accept": "video/mp4"}), timeout=120) as response, temp_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
        if temp_path.stat().st_size == 0:
            raise CliError("下载到的 MP4 是空文件")
        if output_path.exists() and overwrite:
            output_path.unlink()
        temp_path.replace(output_path)
    except (HTTPError, URLError, TimeoutError) as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise CliError(f"视频下载失败：{exc}") from exc
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return digest.hexdigest()


def poll_record(record_path: Path, once: bool, interval: float, max_interval: float, timeout: float) -> dict[str, Any]:
    record = read_json(record_path)
    api_key = auth_key(str(record["api"].get("api_key_env") or DEFAULT_API_KEY_ENV))
    query_template = str(record["api"]["query_endpoint_template"])
    url = query_template.replace("{task_id}", str(record["task_id"]))
    started = time.monotonic()
    wait_for = max(0.1, interval)
    while True:
        response = response_json("GET", url, api_key)
        task = task_from_response(response)
        status = str(task.get("status", "unknown"))
        record["status"] = status
        record["latest_response"] = redact(response, api_key)
        record["updated_at_utc"] = utc_now()
        write_json(record_path, record)
        print(f"task_id={record['task_id']} status={status}")
        if status == "succeeded":
            content = task.get("content", {})
            if not isinstance(content, dict) or not content.get("url"):
                raise CliError("任务显示 succeeded，但响应没有 task.content.url")
            print(f"视频 URL 已返回（限时链接，立即下载）：{content['url']}")
            return record
        if status in {"failed", "cancelled"}:
            raise CliError(f"任务 {status}：{json.dumps(redact(task.get('error', task)), ensure_ascii=False)}")
        if status not in STATUSES:
            raise CliError(f"收到未知任务状态：{status}")
        if once:
            return record
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            record["status"] = "timeout"
            record["updated_at_utc"] = utc_now()
            write_json(record_path, record)
            raise CliError(f"轮询超过 timeout={timeout} 秒，任务仍为 {status}；可稍后重新运行 poll。")
        time.sleep(min(wait_for, max(0.1, timeout - elapsed)))
        wait_for = min(max_interval, wait_for * 1.5)


def archive_record(
    record_path: Path,
    archive_dir: Path,
    segment_id: str | None,
    video_url: str | None,
    tail: bool,
    enhance_tail: bool,
    tail_scale: float,
    overwrite: bool,
) -> dict[str, Any]:
    record = read_json(record_path)
    video_url = video_url or response_video_url(record)
    label = segment_id or record.get("segment_id") or str(record.get("task_id"))
    safe_label = re.sub(r"[^0-9A-Za-z._-]+", "_", str(label))
    archive_dir.mkdir(parents=True, exist_ok=True)
    video_path = archive_dir / f"{safe_label}-actual.mp4"
    video_sha = download_url(video_url, video_path, overwrite=overwrite)
    media_info = ffprobe_video(video_path)
    tail_info: dict[str, Any] | None = None
    tail_path: Path | None = None
    enhanced_tail_info: dict[str, Any] | None = None
    enhanced_tail_path: Path | None = None
    if tail:
        tail_path = archive_dir / f"{safe_label}-F-actual.png"
        tail_info = extract_tail_frame(video_path, tail_path, overwrite=overwrite)
        if enhance_tail:
            enhanced_tail_path = archive_dir / f"{safe_label}-F-enhanced-{tail_scale_label(tail_scale)}.png"
            enhanced_tail_info = enhance_tail_frame(input_path=tail_path, output_path=enhanced_tail_path, scale=tail_scale, overwrite=overwrite)
    manifest_path = archive_dir / f"{safe_label}-manifest.json"
    manifest = {
        "schema_version": 1,
        "segment_id": label,
        "task_id": record.get("task_id"),
        "preview_sha256": record.get("preview_sha256"),
        "video_url_downloaded": video_url,
        "video": {"path": str(video_path.resolve()), "sha256": video_sha, "media": media_info},
        "tail_frame": tail_info,
        "tail_frame_enhanced": enhanced_tail_info,
        "request": record.get("request"),
        "created_at_utc": utc_now(),
    }
    if manifest_path.exists() and not overwrite:
        raise CliError(f"manifest 已存在（如需覆盖请传 --overwrite）：{manifest_path}")
    write_json(manifest_path, manifest)
    record["archive"] = {
        "video_path": str(video_path.resolve()),
        "video_sha256": video_sha,
        "tail_frame_path": str(tail_path.resolve()) if tail_path else None,
        "tail_frame_enhanced_path": str(enhanced_tail_path.resolve()) if enhanced_tail_path else None,
        "manifest_path": str(manifest_path.resolve()),
    }
    record["updated_at_utc"] = utc_now()
    write_json(record_path, record)
    print(f"视频已保存：{video_path.resolve()}")
    if tail_path:
        print(f"真实尾帧已保存：{tail_path.resolve()}")
        print(f"尾帧 sha256：{tail_info['sha256']}")
    if enhanced_tail_path and enhanced_tail_info:
        print(f"轻度增强尾帧已保存：{enhanced_tail_path.resolve()}")
        print(f"增强尾帧 sha256：{enhanced_tail_info['enhanced_sha256']} | 尺寸：{enhanced_tail_info['enhanced_width']}×{enhanced_tail_info['enhanced_height']}")
    print(f"无密钥 manifest：{manifest_path.resolve()}")
    return manifest


def add_prepare_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--content-json", help="API 风格 content 数组 JSON；不能与 prompt/参考参数混用")
    parser.add_argument("--reference-image", action="append", default=[])
    parser.add_argument("--character", action="append", choices=sorted(PROJECT_CHARACTER_REFERENCES), default=[], help="从项目人物锁定目录加入角色参考图，可重复传 programmer/boss/hr")
    parser.add_argument("--character-reference", action="append", default=[], help="加入自定义人物参考图，格式为 character_id=路径；可重复传")
    parser.add_argument("--project-root", help="项目根目录；使用 --character 时默认从当前目录向上查找")
    parser.add_argument("--reference-video", action="append", default=[])
    parser.add_argument("--reference-audio", action="append", default=[])
    parser.add_argument("--first-frame")
    parser.add_argument("--last-frame")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resolution", choices=["768P", "2K"], default=DEFAULT_RESOLUTION)
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--ratio", choices=sorted(RATIOS), default=DEFAULT_RATIO)
    parser.add_argument("--aigc-watermark", action="store_true")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--query-base-url", default=None)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--segment-id")


def add_confirm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--request", required=True, help="prepare 生成的预览 JSON")
    parser.add_argument("--confirm", action="store_true", help="用户已在对话中确认这份预览")
    parser.add_argument("--confirm-sha256", required=True, help="prepare 输出的 preview_sha256")
    parser.add_argument("--record-dir", required=True)


def command_prepare(args: argparse.Namespace) -> int:
    preview = preview_from_args(args)
    output = Path(args.output).expanduser().resolve()
    write_json(output, preview)
    print_preview(preview, output)
    return 0


def command_submit(args: argparse.Namespace) -> int:
    record_path, _ = submit_preview(Path(args.request).expanduser().resolve(), args.confirm, args.confirm_sha256, Path(args.record_dir).expanduser().resolve())
    if args.wait:
        poll_record(record_path, once=False, interval=args.interval, max_interval=args.max_interval, timeout=args.timeout)
    return 0


def command_poll(args: argparse.Namespace) -> int:
    poll_record(Path(args.record).expanduser().resolve(), once=args.once, interval=args.interval, max_interval=args.max_interval, timeout=args.timeout)
    return 0


def command_download(args: argparse.Namespace) -> int:
    archive_record(
        Path(args.record).expanduser().resolve(),
        Path(args.archive_dir).expanduser().resolve(),
        args.segment_id,
        args.video_url,
        not args.no_tail,
        not args.no_enhance_tail,
        args.tail_scale,
        args.overwrite,
    )
    return 0


def command_extract_tail(args: argparse.Namespace) -> int:
    video_path = Path(args.video).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    info = extract_tail_frame(video_path, output_path, args.overwrite)
    print(f"尾帧已保存：{info['tail_frame']}")
    print(f"sha256：{info['sha256']}")
    if args.enhanced_output:
        enhanced_info = enhance_tail_frame(
            output_path,
            Path(args.enhanced_output).expanduser().resolve(),
            scale=args.scale,
            overwrite=args.overwrite,
        )
        info["tail_frame_enhanced"] = enhanced_info
        print(f"轻度增强尾帧已保存：{enhanced_info['enhanced_frame']}")
        print(f"增强尾帧 sha256：{enhanced_info['enhanced_sha256']} | 尺寸：{enhanced_info['enhanced_width']}×{enhanced_info['enhanced_height']}")
    if args.metadata:
        write_json(Path(args.metadata).expanduser().resolve(), info)
        print(f"尾帧 metadata：{Path(args.metadata).expanduser().resolve()}")
    return 0


def command_enhance_tail(args: argparse.Namespace) -> int:
    info = enhance_tail_frame(
        Path(args.input).expanduser().resolve(),
        Path(args.output).expanduser().resolve(),
        scale=args.scale,
        overwrite=args.overwrite,
    )
    print(f"轻度增强尾帧已保存：{info['enhanced_frame']}")
    print(f"原始尺寸：{info['source_width']}×{info['source_height']} | 增强尺寸：{info['enhanced_width']}×{info['enhanced_height']}")
    print(f"原始 sha256：{info['source_sha256']}")
    print(f"增强 sha256：{info['enhanced_sha256']}")
    if args.metadata:
        metadata_path = Path(args.metadata).expanduser().resolve()
        write_json(metadata_path, info)
        print(f"增强尾帧 metadata：{metadata_path}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    record_path, _ = submit_preview(Path(args.request).expanduser().resolve(), args.confirm, args.confirm_sha256, Path(args.record_dir).expanduser().resolve())
    poll_record(record_path, once=False, interval=args.interval, max_interval=args.max_interval, timeout=args.timeout)
    archive_record(
        record_path,
        Path(args.archive_dir).expanduser().resolve(),
        args.segment_id,
        None,
        not args.no_tail,
        not args.no_enhance_tail,
        args.tail_scale,
        args.overwrite,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="安全的 MiniMax-H3 预览、提交、轮询、下载和尾帧工具")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="生成请求预览，不联网、不读取 key")
    add_prepare_args(prepare)
    prepare.add_argument("--output", required=True)
    prepare.set_defaults(func=command_prepare)

    submit = sub.add_parser("submit", help="用户确认后提交一个预览")
    add_confirm_args(submit)
    submit.add_argument("--wait", action="store_true")
    submit.add_argument("--interval", type=float, default=10.0)
    submit.add_argument("--max-interval", type=float, default=30.0)
    submit.add_argument("--timeout", type=float, default=1800.0)
    submit.set_defaults(func=command_submit)

    poll = sub.add_parser("poll", help="轮询已有任务记录")
    poll.add_argument("--record", required=True)
    poll.add_argument("--once", action="store_true")
    poll.add_argument("--interval", type=float, default=10.0)
    poll.add_argument("--max-interval", type=float, default=30.0)
    poll.add_argument("--timeout", type=float, default=1800.0)
    poll.set_defaults(func=command_poll)

    download = sub.add_parser("download", help="下载成功视频、保存真实尾帧并生成轻度增强副本")
    download.add_argument("--record", required=True)
    download.add_argument("--archive-dir", required=True)
    download.add_argument("--segment-id")
    download.add_argument("--video-url")
    download.add_argument("--no-tail", action="store_true")
    download.add_argument("--no-enhance-tail", action="store_true", help="只保存原始尾帧，不生成增强副本")
    download.add_argument("--tail-scale", type=float, default=DEFAULT_TAIL_SCALE, help="尾帧增强倍率，默认 2.0")
    download.add_argument("--overwrite", action="store_true")
    download.set_defaults(func=command_download)

    tail = sub.add_parser("extract-tail", help="从本地视频提取尾帧，可选生成轻度增强副本")
    tail.add_argument("--video", required=True)
    tail.add_argument("--output", required=True)
    tail.add_argument("--metadata")
    tail.add_argument("--enhanced-output", help="可选的增强尾帧 PNG 输出路径")
    tail.add_argument("--scale", type=float, default=DEFAULT_TAIL_SCALE, help="增强倍率，默认 2.0")
    tail.add_argument("--overwrite", action="store_true")
    tail.set_defaults(func=command_extract_tail)

    enhance = sub.add_parser("enhance-tail", help="对已有尾帧做非生成式轻度放大和锐化")
    enhance.add_argument("--input", required=True, help="原始尾帧图片；不会被覆盖")
    enhance.add_argument("--output", required=True, help="增强后的 PNG 输出路径")
    enhance.add_argument("--metadata")
    enhance.add_argument("--scale", type=float, default=DEFAULT_TAIL_SCALE, help="增强倍率，默认 2.0")
    enhance.add_argument("--overwrite", action="store_true")
    enhance.set_defaults(func=command_enhance_tail)

    run = sub.add_parser("run", help="确认后提交、轮询、下载并保存原始/增强尾帧")
    add_confirm_args(run)
    run.add_argument("--archive-dir", required=True)
    run.add_argument("--segment-id")
    run.add_argument("--no-tail", action="store_true")
    run.add_argument("--no-enhance-tail", action="store_true", help="只保存原始尾帧，不生成增强副本")
    run.add_argument("--tail-scale", type=float, default=DEFAULT_TAIL_SCALE, help="尾帧增强倍率，默认 2.0")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--interval", type=float, default=10.0)
    run.add_argument("--max-interval", type=float, default=30.0)
    run.add_argument("--timeout", type=float, default=1800.0)
    run.set_defaults(func=command_run)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
