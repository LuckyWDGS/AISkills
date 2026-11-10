"""Search the dated public-reference snapshot without loading it into a prompt."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import re
import sys


DEFAULT_LIBRARY = Path(__file__).resolve().parents[1] / "references" / "case-library" / "cases.json"


def as_of_date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("use a valid YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use a valid YYYY-MM-DD date") from exc


def freshness_on(work: dict, as_of: date) -> str:
    """Reclassify full displayed calendar dates; never infer a year or timezone."""
    raw = work.get("published_at_raw")
    if not raw:
        return "unknown"
    match = re.search(r"(?<!\d)(\d{4})[-年](\d{1,2})[-月](\d{1,2})(?:日)?(?!\d)", str(raw))
    if not match:
        return "date_unverified"
    try:
        published = date(*(int(part) for part in match.groups()))
    except ValueError:
        return "date_unverified"
    age = (as_of - published).days
    if age < 0:
        return "future_date"
    if age <= 6:
        return "within_7_calendar_days"
    if age <= 29:
        return "within_30_calendar_days_outside_7"
    return "historical"


def select_cases(works: list[dict], args: argparse.Namespace) -> list[dict]:
    def contains(value: str | None, needle: str | None) -> bool:
        return needle is None or needle.casefold() in (value or "").casefold()

    selected = []
    for work in works:
        if args.id and work["work_id"] != args.id:
            continue
        if not contains(work.get("author"), args.author):
            continue
        if args.platform and work["platform"] != args.platform:
            continue
        if args.grade and work["evidence_grade"] != args.grade:
            continue
        if args.dense and not work.get("dense_review"):
            continue
        if args.role and args.role not in (work.get("sample_roles") or []):
            continue
        if args.layer and not contains(work.get("research_layer"), args.layer):
            continue
        if args.content_format and not contains(work.get("content_format"), args.content_format):
            continue
        if args.task and not any(contains(t, args.task) for t in work.get("viewer_tasks") or []):
            continue
        if args.freshness and work.get("freshness_current") != args.freshness:
            continue
        if args.family and not any(contains(f, args.family) for f in work["families"]):
            continue
        if args.tag and not any(contains(t, args.tag.lstrip("#")) for t in work.get("actual_hashtags") or []):
            continue
        if args.query:
            text = " ".join(str(work.get(k) or "") for k in ("title_excerpt", "view_scope", "visual_observation", "sample_role_note", "content_format", "viewer_tasks"))
            if not contains(text, args.query):
                continue
        selected.append(work)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--id", help="Exact platform work ID")
    parser.add_argument("--author", help="Author name substring")
    parser.add_argument("--platform", choices=("douyin", "bilibili"))
    parser.add_argument("--grade", choices=("A", "B", "C", "D"))
    parser.add_argument("--dense", action="store_true", help="Only works with completed full 4fps visual-review records; B alone also includes sparse samples")
    parser.add_argument("--role", choices=("user_seed", "ordinary_control"), help="Recorded sampling role; missing role is not inferred")
    parser.add_argument("--layer", help="Research layer, e.g. finished_content_reference or production_tutorial")
    parser.add_argument("--format", dest="content_format", help="Dynamically established content format substring; unclassified records remain unclassified")
    parser.add_argument("--task", help="Dynamically established viewing task, e.g. choose/enter/stay/arrive/learn")
    parser.add_argument("--as-of", type=as_of_date, help="Recompute calendar windows from full displayed publication dates without changing the library or refreshing metrics")
    parser.add_argument("--freshness", choices=("within_7_calendar_days", "within_30_calendar_days_outside_7", "historical", "unknown", "date_unverified", "future_date"), help="Publication-date group at --as-of, or the library's recorded as-of if omitted; not today's popularity")
    parser.add_argument("--family", help="Research classification substring, not an author hashtag")
    parser.add_argument("--tag", help="Observed author hashtag substring")
    parser.add_argument("--query", help="Search title and documented visual scope")
    parser.add_argument("--limit", type=int, default=12, help="Maximum printed results; 0 prints all")
    parser.add_argument("--summary", action="store_true", help="Summarize matching records")
    parser.add_argument("--summary-limit", type=int, default=20, help="Maximum authors/tags printed per summary group; 0 prints all, complete matched count is unchanged")
    parser.add_argument("--json", action="store_true", help="Return full matching records as JSON")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    if args.summary_limit < 0:
        parser.error("--summary-limit must be nonnegative")
    try:
        data = json.loads(args.library.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Cannot read case library: {exc}\n")
    works = data["works"]
    keys = [(w["platform"], w["work_id"]) for w in works]
    if len(set(keys)) != len(keys):
        parser.exit(2, "Duplicate platform/work IDs in library\n")
    if args.as_of:
        works = [dict(w, freshness_current=freshness_on(w, args.as_of), freshness_current_as_of=args.as_of.isoformat()) for w in works]
    selected = select_cases(works, args)
    context = {
        "snapshot_date": data["snapshot_date"],
        "timezone": data["timezone"],
        "matched_unique_works": len(selected),
        "platform_counts": dict(Counter(w["platform"] for w in selected)),
        "freshness_query_as_of": args.as_of.isoformat() if args.as_of else None,
        "freshness_query_basis": "full displayed calendar date; no timezone conversion, relative-date inference or network refresh" if args.as_of else "recorded library groups; consult freshness_current_as_of for each record",
        "note": "Dated research snapshot. Counts are not completed watches or current popularity.",
    }
    if args.as_of:
        context["calendar_windows"] = {"last7_inclusive": [(args.as_of - timedelta(days=6)).isoformat(), args.as_of.isoformat()], "last30_inclusive": [(args.as_of - timedelta(days=29)).isoformat(), args.as_of.isoformat()], "publication_timezone": "not inferred"}
    if args.summary:
        def capped(counter: Counter) -> dict:
            return dict(counter.most_common(args.summary_limit or None))
        context["evidence_grades"] = dict(sorted(Counter(w["evidence_grade"] for w in selected).items()))
        author_counts = Counter(w.get("author") or "unknown" for w in selected)
        context["authors"] = capped(author_counts)
        context["recorded_canonical_profiles"] = len({w["author_url"].split("?")[0].rstrip("/") for w in selected if w.get("author_url")})
        context["dense_4fps_reviewed_works"] = sum(bool(w.get("dense_review")) for w in selected)
        context["research_layers"] = dict(Counter(w.get("research_layer") or "unclassified" for w in selected))
        context["content_formats"] = dict(Counter(w.get("content_format") or "unclassified" for w in selected))
        context["viewer_tasks"] = dict(Counter(t for w in selected for t in w.get("viewer_tasks") or []))
        context["sample_roles"] = dict(Counter(t for w in selected for t in w.get("sample_roles") or []))
        freshness_key = "freshness_at_query_as_of" if args.as_of else "freshness_at_recorded_as_of"
        context[freshness_key] = dict(Counter(w.get("freshness_current") or "not_recomputed" for w in selected))
        context["research_families"] = dict(Counter(f for w in selected for f in w["families"]).most_common())
        tag_counts = Counter(t for w in selected for t in set(w.get("actual_hashtags") or []))
        context["actual_tag_work_counts"] = capped(tag_counts)
        tag_profiles: dict[str, set[str]] = {}
        tag_names: dict[str, set[str]] = {}
        for work in selected:
            for tag in set(work.get("actual_hashtags") or []):
                if work.get("author_url"):
                    tag_profiles.setdefault(tag, set()).add(work["author_url"].split("?")[0].rstrip("/"))
                if work.get("author"):
                    tag_names.setdefault(tag, set()).add(work["author"])
        context["actual_tag_profile_counts"] = {t: len(tag_profiles.get(t, set())) for t in context["actual_tag_work_counts"]}
        context["actual_tag_display_name_counts"] = {t: len(tag_names.get(t, set())) for t in context["actual_tag_work_counts"]}
        context["summary_groups"] = {"limit":args.summary_limit, "author_groups_total":len(author_counts), "author_groups_shown":len(context["authors"]), "tag_groups_total":len(tag_counts), "tag_groups_shown":len(context["actual_tag_work_counts"]), "expand_all":"--summary-limit 0"}
        context["tag_coverage_unique_works"] = sum(w.get("actual_hashtags") is not None for w in selected)
        context["tag_note"] = "Sample-library usage only; not platform search volume or recommendation weight."
        print(json.dumps(context, ensure_ascii=False, indent=2))
        return 0
    shown = selected if args.limit == 0 else selected[: args.limit]
    if args.json:
        print(json.dumps({**context, "shown": len(shown), "works": shown}, ensure_ascii=False, indent=2))
        return 0
    print(f"Snapshot {data['snapshot_date']} ({data['timezone']}); {len(selected)} matches, showing {len(shown)}.")
    print(context["note"])
    if args.as_of:
        print(f"Publication windows recomputed as of {args.as_of}; metrics and trend data were not refreshed.")
    for work in shown:
        print(f"\n[{work['evidence_grade']}] {work.get('author') or 'unknown'} | {work['work_id']}")
        print(work["title_excerpt"])
        print(work["url"])
        print(f"Research families: {', '.join(work['families'])}")
        dense = work.get("dense_review")
        if dense:
            sample_count = dense.get("sample_count", dense.get("reviewed_sample_count"))
            print(f"Visual depth: full 4fps temporal samples inspected; {sample_count} samples / {len(dense['reviewed_sheets'])} sheets; not continuous audiovisual viewing")
        else:
            print("Visual depth: no completed full 4fps review; refer to recorded scope")
        print(f"View scope: {work['view_scope']}; audio: {work['audio_review']}")
        tags = work.get("actual_hashtags")
        print("Observed hashtags: " + ("not collected" if tags is None else ", ".join(tags) or "none found in recorded scope"))
        if work.get("visual_observation"):
            print("Documented visual observation: " + work["visual_observation"])
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
