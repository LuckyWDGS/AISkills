from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text


VALID_RENDERERS = {
    "sprite",
    "ribbon",
    "mesh",
    "decal",
    "surface",
    "landscape",
    "ui",
    "post_process",
    "unknown",
}


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_contract(args: argparse.Namespace) -> dict[str, Any]:
    renderer = args.renderer.lower()
    return {
        "tool": "material_contract",
        "version": 1,
        "created_utc": utc_now_iso(),
        "effect": args.effect,
        "layer": args.layer,
        "owner_model": {
            "vfx_lead": "niagara-vfx-artist",
            "material_specialist": "unreal-material-artist",
        },
        "carrier": {
            "renderer": renderer,
            "uv_expectations": args.uv,
            "particle_inputs": split_csv(args.particle_inputs),
            "dynamic_parameters": split_csv(args.dynamic_parameters),
            "sort_or_depth_notes": args.sort_notes,
        },
        "material": {
            "domain": args.domain,
            "blend_mode": args.blend_mode,
            "shading_model": args.shading_model,
            "two_sided": args.two_sided,
            "expected_outputs": split_csv(args.outputs),
            "usage_flags": split_csv(args.usage_flags),
        },
        "textures": [],
        "parameters": [],
        "budgets": {
            "platform": args.platform,
            "instruction_budget": args.instruction_budget,
            "sampler_budget": args.sampler_budget,
            "texture_memory_budget_mb": args.texture_memory_budget_mb,
            "overdraw_risk": args.overdraw_risk,
        },
        "acceptance": split_csv(args.acceptance),
        "notes": args.notes,
    }


def validate_contract(contract: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not contract.get("effect"):
        add("error", "missing_effect", "Contract is missing an effect name.")
    if not contract.get("layer"):
        add("error", "missing_layer", "Contract is missing a material layer name.")

    carrier = contract.get("carrier") or {}
    renderer = str(carrier.get("renderer") or "unknown").lower()
    if renderer not in VALID_RENDERERS:
        add("warning", "unknown_renderer", f"Renderer '{renderer}' is not one of {sorted(VALID_RENDERERS)}.")
    if renderer in {"sprite", "ribbon", "mesh"} and not carrier.get("particle_inputs"):
        add("warning", "missing_particle_inputs", "Niagara material should state ParticleColor or DynamicParameter usage.")

    material = contract.get("material") or {}
    blend_mode = str(material.get("blend_mode") or "").lower()
    if not material.get("expected_outputs"):
        add("warning", "missing_outputs", "Expected material outputs are not listed.")
    if blend_mode in {"translucent", "additive"} and not carrier.get("sort_or_depth_notes"):
        add("warning", "missing_sort_notes", "Translucent/additive materials should record sorting, depth, or overdraw risks.")

    budgets = contract.get("budgets") or {}
    if budgets.get("instruction_budget") is None:
        add("warning", "missing_instruction_budget", "No instruction budget is listed.")
    if budgets.get("sampler_budget") is None:
        add("warning", "missing_sampler_budget", "No sampler budget is listed.")
    if not budgets.get("platform"):
        add("warning", "missing_platform", "No target platform is listed.")

    for texture in contract.get("textures") or []:
        role = str(texture.get("role") or "unknown").lower()
        if role in {"mask", "packed", "flow", "normal"} and texture.get("srgb") is not False:
            add("warning", "texture_srgb", f"Texture '{texture.get('name')}' role '{role}' should usually have sRGB disabled.")
        if role in {"flipbook", "atlas"} and not texture.get("grid"):
            add("warning", "missing_grid", f"Texture '{texture.get('name')}' should list grid size for SubUV/atlas use.")

    if not contract.get("acceptance"):
        add("warning", "missing_acceptance", "No acceptance checks are listed.")
    return findings


def render_markdown(contract: dict[str, Any], findings: list[dict[str, str]]) -> str:
    material = contract.get("material") or {}
    carrier = contract.get("carrier") or {}
    budgets = contract.get("budgets") or {}
    lines = [
        f"# Material Contract: {contract.get('effect', '')} / {contract.get('layer', '')}",
        "",
        "## Carrier",
        "",
        f"- Renderer: `{carrier.get('renderer', 'unknown')}`",
        f"- UV expectations: {carrier.get('uv_expectations') or 'not specified'}",
        f"- Particle inputs: {', '.join(carrier.get('particle_inputs') or []) or 'not specified'}",
        f"- Dynamic parameters: {', '.join(carrier.get('dynamic_parameters') or []) or 'none'}",
        f"- Sort/depth notes: {carrier.get('sort_or_depth_notes') or 'not specified'}",
        "",
        "## Material Route",
        "",
        f"- Domain: `{material.get('domain', '')}`",
        f"- Blend mode: `{material.get('blend_mode', '')}`",
        f"- Shading model: `{material.get('shading_model', '')}`",
        f"- Two sided: `{material.get('two_sided', False)}`",
        f"- Outputs: {', '.join(material.get('expected_outputs') or []) or 'not specified'}",
        "",
        "## Budgets",
        "",
        f"- Platform: `{budgets.get('platform', '')}`",
        f"- Instruction budget: `{budgets.get('instruction_budget')}`",
        f"- Sampler budget: `{budgets.get('sampler_budget')}`",
        f"- Texture memory budget MB: `{budgets.get('texture_memory_budget_mb')}`",
        f"- Overdraw risk: `{budgets.get('overdraw_risk', '')}`",
        "",
        "## Findings",
        "",
    ]
    if findings:
        for finding in findings:
            lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
    else:
        lines.append("- Contract looks structurally complete.")
    lines.extend(["", "## Acceptance", ""])
    acceptance = contract.get("acceptance") or []
    if acceptance:
        lines.extend(f"- {item}" for item in acceptance)
    else:
        lines.append("- Not specified.")
    if contract.get("notes"):
        lines.extend(["", "## Notes", "", str(contract["notes"])])
    return "\n".join(lines).rstrip() + "\n"


def command_new(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    contract = build_contract(args)
    findings = validate_contract(contract)
    stem = slugify(f"{args.effect}-{args.layer}")
    out = Path(args.out) if args.out else default_report_path(ctx, "contracts", stem, "material-contract", ".json")
    save_json(out, {**contract, "findings": findings})
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(contract, findings))
    print(out)
    return 0


def command_validate(args: argparse.Namespace) -> int:
    import json

    path = Path(args.contract)
    contract = json.loads(path.read_text(encoding="utf-8"))
    findings = validate_contract(contract)
    if args.markdown:
        out = Path(args.out) if args.out else path.with_suffix(".md")
        write_text(out, render_markdown(contract, findings))
        print(out)
    else:
        print(json.dumps({"findings": findings}, ensure_ascii=False, indent=2))
    return 1 if any(item["severity"] == "error" for item in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or validate a Niagara-to-material contract.")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Create a material contract JSON.")
    new.add_argument("--root", default="auto")
    new.add_argument("--effect", required=True)
    new.add_argument("--layer", required=True)
    new.add_argument("--renderer", default="unknown")
    new.add_argument("--uv", default="")
    new.add_argument("--particle-inputs", default="ParticleColor")
    new.add_argument("--dynamic-parameters", default="")
    new.add_argument("--sort-notes", default="")
    new.add_argument("--domain", default="Surface")
    new.add_argument("--blend-mode", default="Additive")
    new.add_argument("--shading-model", default="Unlit")
    new.add_argument("--two-sided", action="store_true")
    new.add_argument("--outputs", default="EmissiveColor,Opacity")
    new.add_argument("--usage-flags", default="")
    new.add_argument("--platform", default="PC")
    new.add_argument("--instruction-budget", type=int, default=120)
    new.add_argument("--sampler-budget", type=int, default=4)
    new.add_argument("--texture-memory-budget-mb", type=float)
    new.add_argument("--overdraw-risk", default="medium")
    new.add_argument("--acceptance", default="")
    new.add_argument("--notes", default="")
    new.add_argument("--out")
    new.add_argument("--markdown", action="store_true")
    new.set_defaults(func=command_new)

    validate = sub.add_parser("validate", help="Validate an existing material contract JSON.")
    validate.add_argument("contract")
    validate.add_argument("--out")
    validate.add_argument("--markdown", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
