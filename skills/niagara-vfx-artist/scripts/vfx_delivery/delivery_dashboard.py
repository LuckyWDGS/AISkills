from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from .core import normalize_cli_global_args_no_subcommand, resolve_root_context, save_json, utc_now_iso, write_text
from .delivery_package import delivery_payload_health, health_badge


def load_delivery_indexes(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    indexes: list[tuple[Path, dict[str, Any]]] = []
    if not root.exists():
        return indexes
    for path in root.rglob("delivery-index.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            indexes.append((path, payload))
    indexes.sort(key=lambda item: (str(item[1].get("overall", "")), str(item[1].get("effect_name", ""))))
    return indexes


def open_gate_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    health = delivery_payload_health(payload)
    rows: list[dict[str, str]] = []
    for key, item in (health.get("checks") or {}).items():
        status = str(item.get("status", "unknown") or "unknown")
        if status in {"pass", "not_applicable"}:
            continue
        rows.append(
            {
                "key": key,
                "label": str(item.get("label", key)),
                "status": status,
                "detail": str(item.get("detail", "")),
                "action_needed": str(item.get("action_needed", "")),
            }
        )
    return rows


def build_dashboard(ctx) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for path, payload in load_delivery_indexes(ctx.vfx_root / "delivery"):
        health = delivery_payload_health(payload)
        overall = str(health.get("overall") or payload.get("overall") or "unknown")
        counts[overall] = counts.get(overall, 0) + 1
        rows.append(
            {
                "effect_name": payload.get("effect_name", ""),
                "overall": overall,
                "index_path": str(path),
                "summary_path": str((payload.get("outputs") or {}).get("summary", "")),
                "manifest_path": str((payload.get("outputs") or {}).get("manifest", "")),
                "final_systems": payload.get("final_systems", []),
                "final_materials": payload.get("final_materials", []),
                "open_gates": open_gate_rows(payload),
            }
        )
    return {
        "tool": "delivery_dashboard",
        "generated_utc": utc_now_iso(),
        "root": str(ctx.project_root),
        "counts": counts,
        "packages": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# VFX Delivery Dashboard",
        "",
        f"- Generated UTC: `{report.get('generated_utc', '')}`",
        f"- Root: `{report.get('root', '')}`",
        "",
        "## Counts",
        "",
    ]
    counts = report.get("counts") or {}
    if counts:
        for key in sorted(counts):
            lines.append(f"- {health_badge(key)}: `{counts[key]}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Packages", ""])
    for item in report.get("packages", []):
        lines.append(f"- `{item.get('effect_name') or 'unknown'}`: `{health_badge(str(item.get('overall', 'unknown')))}`")
        if item.get("summary_path"):
            lines.append(f"  Summary: `{item['summary_path']}`")
        for gate in item.get("open_gates", []):
            lines.append(f"  Gate {gate['label']}: `{health_badge(gate['status'])}` - {gate['detail']}")
            if gate.get("action_needed"):
                lines.append(f"  Action: {gate['action_needed']}")
    if not report.get("packages"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def render_html(report: dict[str, Any]) -> str:
    status_order = {"ready": 0, "risk": 1, "blocked": 2, "incomplete": 3, "unknown": 4}
    packages = sorted(report.get("packages", []), key=lambda item: (status_order.get(str(item.get("overall")), 9), str(item.get("effect_name", ""))))
    cards: list[str] = []
    for item in packages:
        overall = str(item.get("overall", "unknown"))
        gates = item.get("open_gates", [])
        gate_html = "".join(
            f"<li><strong>{html.escape(gate.get('label', ''))}</strong>: {html.escape(gate.get('status', ''))}<br><span>{html.escape(gate.get('detail', ''))}</span><br><code>{html.escape(gate.get('action_needed', ''))}</code></li>"
            for gate in gates
        ) or "<li>All required gates are closed.</li>"
        cards.append(
            f"""
            <section class="card {html.escape(overall)}">
              <div class="card-head">
                <h2>{html.escape(str(item.get('effect_name') or 'unknown'))}</h2>
                <span class="badge">{html.escape(health_badge(overall))}</span>
              </div>
              <p><b>Systems:</b> {html.escape(', '.join(item.get('final_systems', [])) or 'none')}</p>
              <p><b>Materials:</b> {html.escape(', '.join(item.get('final_materials', [])) or 'none')}</p>
              <p><b>Index:</b> <code>{html.escape(str(item.get('index_path', '')))}</code></p>
              <p><b>Summary:</b> <code>{html.escape(str(item.get('summary_path', '')))}</code></p>
              <ul>{gate_html}</ul>
            </section>
            """
        )
    counts = "".join(
        f"<span class='count'><b>{html.escape(health_badge(key))}</b> {value}</span>"
        for key, value in sorted((report.get("counts") or {}).items())
    ) or "<span class='count'><b>NONE</b> 0</span>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>VFX Delivery Dashboard</title>
  <style>
    body {{ margin: 0; font-family: "Segoe UI", sans-serif; background: #11151c; color: #e9edf5; }}
    header {{ padding: 28px 34px; background: linear-gradient(135deg, #19212e, #27384e); border-bottom: 1px solid #3b4b63; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    main {{ padding: 24px 34px; display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }}
    .counts {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .count {{ background: #0f141b; border: 1px solid #42536c; border-radius: 999px; padding: 8px 12px; }}
    .card {{ background: #161d27; border: 1px solid #314056; border-radius: 18px; padding: 18px; box-shadow: 0 18px 50px rgba(0,0,0,.25); }}
    .card.ready {{ border-color: #2da66f; }}
    .card.risk {{ border-color: #d89b28; }}
    .card.blocked, .card.incomplete {{ border-color: #c75151; }}
    .card-head {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
    h2 {{ margin: 0; font-size: 18px; }}
    .badge {{ border-radius: 999px; padding: 6px 10px; background: #253246; font-weight: 700; }}
    p, li {{ color: #c8d2e1; line-height: 1.45; }}
    code {{ color: #9bd1ff; word-break: break-all; }}
    ul {{ padding-left: 20px; }}
  </style>
</head>
<body>
  <header>
    <h1>VFX Delivery Dashboard</h1>
    <p>Generated UTC: <code>{html.escape(str(report.get('generated_utc', '')))}</code></p>
    <p>Root: <code>{html.escape(str(report.get('root', '')))}</code></p>
    <div class="counts">{counts}</div>
  </header>
  <main>{''.join(cards) or '<p>No delivery packages found.</p>'}</main>
</body>
</html>
"""


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    report = build_dashboard(ctx)
    out = Path(args.out) if args.out else ctx.vfx_root / "delivery-dashboard" / "delivery-dashboard.json"
    save_json(out, report)
    if args.markdown:
        markdown_out = Path(args.markdown_out) if args.markdown_out else out.with_suffix(".md")
        write_text(markdown_out, render_markdown(report))
    if args.html:
        html_out = Path(args.html_out) if args.html_out else out.with_suffix(".html")
        write_text(html_out, render_html(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize all VFX delivery-index.json files for batch review and daily status.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--html-out", default="")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args_no_subcommand(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
