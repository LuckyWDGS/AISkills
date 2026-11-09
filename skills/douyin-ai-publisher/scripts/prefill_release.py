#!/usr/bin/env python3
"""Draft and check Douyin release packages.

draft: build a release.json draft from inspect_media.py's media_report.json
       (+ the account's operations.json). The draft carries a `_draft` marker,
       so release_ledger.py refuses to register it until it is completed.
check: list what a release.json still lacks before registration.

Never uploads or publishes. Never overwrites an existing release.json.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "templates" / "release.template.json"
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
UNSET = (None, "", "unverified")

REQUIRED = [
    ("account_id", "核验后的账号 ID"),
    ("observed_at", "采集时间"),
    ("timezone", "时区"),
    ("kind", "体裁 video/image"),
    ("content_facts.visible_summary", "内容事实概述"),
    ("content_facts.visual_review.status", "画面核验状态"),
    ("content_facts.audio_review.status", "声音核验状态（图文写 not_applicable）"),
    ("audience_value.promise", "观众价值"),
    ("follow_reason", "关注理由"),
    ("title", "确定标题"),
    ("caption", "正文"),
    ("cover.source", "封面来源"),
    ("disclosures.ai.required", "是否需要 AI 声明"),
    ("rights.status", "权利核验状态"),
    ("publication.mode", "草稿/立即/定时"),
    ("publication.visibility", "可见范围"),
    ("publication.submission_policy", "提交分工"),
]


def home() -> Path:
    return Path(os.environ.get("DOUYIN_PUBLISHER_HOME") or Path.home() / ".douyin-publisher").expanduser()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dig(data: dict, dotted: str):
    node = data
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def draft(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser().resolve()
    if out.exists():
        print(json.dumps({"ok": False, "error": "out_exists", "message": f"{out} 已存在；不覆盖。修订请另存新目录。"}, ensure_ascii=False), file=sys.stderr)
        return 1
    report_path = Path(args.report).expanduser().resolve()
    report = load_json(report_path)
    media = report.get("media") or []
    if not media:
        print(json.dumps({"ok": False, "error": "empty_report"}), file=sys.stderr)
        return 1
    if report.get("kind") not in {"video", "image"}:
        print(json.dumps({"ok": False, "error": "kind_unclear", "message": "报告中素材类型为空或混合；视频和图片请分开发布。"}, ensure_ascii=False), file=sys.stderr)
        return 1

    operations = {}
    ops_path = Path(args.operations).expanduser() if args.operations else None
    if ops_path is None and args.account:
        if not ACCOUNT_RE.match(args.account):
            print(json.dumps({"ok": False, "error": "invalid_account"}), file=sys.stderr)
            return 1
        candidate = home() / args.account / "operations.json"
        ops_path = candidate if candidate.is_file() else None
    if ops_path is not None:
        operations = load_json(ops_path)

    pkg = load_json(TEMPLATE)
    pkg.pop("_template", None)
    pkg = copy.deepcopy(pkg)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    policy = (operations.get("submission_policy") or {}).get("mode") or "handoff"
    account = args.account or (operations.get("account") or {}).get("account_id")
    user_tz = operations.get("user_timezone")

    warnings = [dict(c, media_index=m["index"]) for m in media for c in m.get("checks", []) if c["level"] == "warn"]
    blocks = [dict(c, media_index=m["index"]) for m in media for c in m.get("checks", []) if c["level"] == "block"]
    first = media[0]
    loud = first.get("loudness") or {}

    pkg["_draft"] = {
        "status": "draft",
        "registerable": False,
        "created_at": now,
        "note": "由 prefill_release.py 生成。补齐缺项、记录每条 warn 的处理后删除本字段，再用 check 确认并登记。",
    }
    pkg.update({
        "account_id": account,
        "observed_at": now,
        "timezone": user_tz,
        "kind": report["kind"],
        "ordered_media": [{"index": m["index"], "path": m["path"], "sha256": m.get("sha256")} for m in media],
    })
    facts = pkg["content_facts"]
    if report["kind"] == "video":
        facts["duration_seconds"] = first.get("duration_seconds")
        facts["visual_review"]["method"] = f"inspect_media.py 关键帧 {first.get('keyframe_sheet')} 与推荐流预览 {first.get('feed_preview')}；人工查看待完成"
        facts["audio_review"]["method"] = "inspect_media.py 客观测量；人工听审待完成"
        facts["audio_review"]["findings"] = (
            f"整体响度 {loud.get('integrated_lufs')} LUFS，真峰值 {loud.get('true_peak_dbtp')} dBTP，"
            f"静音合计 {loud.get('silence_total_seconds')} 秒" if loud else "无音轨或未测得"
        )
    else:
        facts["image_count"] = len(media)
        facts["visual_review"]["method"] = "inspect_media.py 参数检查；逐张人工查看待完成"
        facts["audio_review"]["status"] = "not_applicable"
    pkg["media_qa"].update({
        "report_path": str(report_path),
        "overall": report.get("overall"),
        "warnings": warnings,
        "blocks": blocks,
        "decisions": [],
    })
    pkg["cover"]["candidates"] = first.get("cover_candidates", []) if report["kind"] == "video" else [m["path"] for m in media[:1]]
    pkg["publication"].update({"user_timezone": user_tz, "submission_policy": policy})
    pkg["pending_items"] = [
        "人工查看关键帧和推荐流预览，填写 content_facts 与 media_qa.manual_review。",
        "为每条 media_qa.warnings 在 media_qa.decisions 记录处理：已修改 / 用户决定照发 / 不适用。",
        "按当次热点和常青话题填写 topics（每条带来源、时间、关联理由）。",
        "确定标题、正文、封面、声明、权利与发布方式。",
        "完成后删除 _draft，运行 prefill_release.py check。",
    ]
    if not account:
        pkg["pending_items"].insert(0, "填写已核验的 account_id（未传 --account，也未找到运营档案）。")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(pkg, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"ok": True, "draft": str(out), "warnings": len(warnings), "blocks": len(blocks),
                      "submission_policy": policy, "operations": str(ops_path) if ops_path else None}, ensure_ascii=False))
    return 0


def check(args: argparse.Namespace) -> int:
    path = Path(args.package).expanduser().resolve()
    pkg = load_json(path)
    problems: list[str] = []
    for marker in ("_draft", "_template"):
        if marker in pkg:
            problems.append(f"仍含 {marker}：补齐后删除该字段")
    for dotted, label in REQUIRED:
        if dig(pkg, dotted) in UNSET:
            problems.append(f"缺 {dotted}（{label}）")
    media = pkg.get("ordered_media") or []
    if not media:
        problems.append("缺 ordered_media")
    for item in media:
        current = file_hash(Path(item.get("path", "")))
        if current is None:
            problems.append(f"素材不存在：{item.get('path')}")
        elif item.get("sha256") and current != item["sha256"]:
            problems.append(f"素材 hash 与检查报告不一致，需重新检查：{item.get('path')}")
    qa = pkg.get("media_qa") or {}
    if qa.get("blocks"):
        problems.append(f"成片检查有 {len(qa['blocks'])} 个 block 未解决")
    decided = {d.get("id") for d in qa.get("decisions", []) if isinstance(d, dict) and d.get("decision")}
    for w in qa.get("warnings", []):
        if w.get("id") not in decided:
            problems.append(f"warn 未记录处理：{w.get('id')}（media_qa.decisions 加 {{\"id\": \"{w.get('id')}\", \"decision\": \"...\"}}）")
    topics = pkg.get("topics")
    if not isinstance(topics, list):
        problems.append("topics 必须是列表（无合适热点可为空列表）")
    else:
        for i, topic in enumerate(topics, 1):
            if not isinstance(topic, dict) or not topic.get("name"):
                problems.append(f"topics[{i}] 缺 name")
                continue
            if not topic.get("content_connection"):
                problems.append(f"话题 {topic['name']} 缺 content_connection（与作品的具体关联）")
            if not topic.get("source_url_or_page") and not topic.get("missing_reason"):
                problems.append(f"话题 {topic['name']} 缺来源或 missing_reason")
    result = {"ok": not problems, "package": str(path), "problems": problems}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("draft", help="从成片检查报告生成 release.json 草稿")
    d.add_argument("--report", required=True, help="inspect_media.py 生成的 media_report.json")
    d.add_argument("--out", required=True, help="输出 release.json 路径（已存在则拒绝）")
    d.add_argument("--account", help="账号 ID；用于读取账号目录下的 operations.json")
    d.add_argument("--operations", help="显式指定 operations.json 路径")
    c = sub.add_parser("check", help="检查 release.json 登记前的缺项")
    c.add_argument("package")
    args = parser.parse_args()
    try:
        return draft(args) if args.command == "draft" else check(args)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
