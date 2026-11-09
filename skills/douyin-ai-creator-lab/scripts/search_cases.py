"""Search the dated public-reference snapshot without loading it into a prompt."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


DEFAULT_LIBRARY = Path(__file__).resolve().parents[1] / "references" / "case-library" / "cases.json"


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
        if args.family and not any(contains(f, args.family) for f in work["families"]):
            continue
        if args.tag and not any(contains(t, args.tag.lstrip("#")) for t in work.get("actual_hashtags") or []):
            continue
        if args.query:
            text = " ".join(str(work.get(k) or "") for k in ("title_excerpt", "view_scope", "visual_observation"))
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
    parser.add_argument("--family", help="Research classification substring, not an author hashtag")
    parser.add_argument("--tag", help="Observed author hashtag substring")
    parser.add_argument("--query", help="Search title and documented visual scope")
    parser.add_argument("--limit", type=int, default=12, help="Maximum printed results; 0 prints all")
    parser.add_argument("--summary", action="store_true", help="Summarize matching records")
    parser.add_argument("--json", action="store_true", help="Return full matching records as JSON")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    try:
        data = json.loads(args.library.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Cannot read case library: {exc}\n")
    works = data["works"]
    keys = [(w["platform"], w["work_id"]) for w in works]
    if len(set(keys)) != len(keys):
        parser.exit(2, "Duplicate platform/work IDs in library\n")
    selected = select_cases(works, args)
    context = {
        "snapshot_date": data["snapshot_date"],
        "timezone": data["timezone"],
        "matched_unique_works": len(selected),
        "note": "Dated research snapshot. Counts are not completed watches or current popularity.",
    }
    if args.summary:
        context["evidence_grades"] = dict(sorted(Counter(w["evidence_grade"] for w in selected).items()))
        context["authors"] = dict(Counter(w.get("author") or "unknown" for w in selected).most_common())
        context["research_families"] = dict(Counter(f for w in selected for f in w["families"]).most_common())
        context["actual_tag_work_counts"] = dict(Counter(t for w in selected for t in set(w.get("actual_hashtags") or [])).most_common())
        tag_profiles: dict[str, set[str]] = {}
        tag_names: dict[str, set[str]] = {}
        for work in selected:
            for tag in set(work.get("actual_hashtags") or []):
                if work.get("author_url"):
                    tag_profiles.setdefault(tag, set()).add(work["author_url"].split("?")[0].rstrip("/"))
                if work.get("author"):
                    tag_names.setdefault(tag, set()).add(work["author"])
        context["actual_tag_profile_counts"] = {t: len(v) for t, v in tag_profiles.items()}
        context["actual_tag_display_name_counts"] = {t: len(v) for t, v in tag_names.items()}
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
    for work in shown:
        print(f"\n[{work['evidence_grade']}] {work.get('author') or 'unknown'} | {work['work_id']}")
        print(work["title_excerpt"])
        print(work["url"])
        print(f"Research families: {', '.join(work['families'])}")
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
