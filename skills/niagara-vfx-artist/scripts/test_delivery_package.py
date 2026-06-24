from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vfx_delivery.core import save_json
from vfx_delivery.delivery_package import build_delivery_health, live_asset_report_passed, main
from vfx_delivery.delivery_dashboard import main as dashboard_main
from vfx_delivery.delivery_finalize import main as finalize_main


def acceptance(anchor_path: Path | None) -> dict:
    return {
        "anchor_lock": {
            "entry_id": "anchor-ready" if anchor_path else "",
            "implementation_scope": "full effect" if anchor_path else "",
            "scope_confirmed": bool(anchor_path),
            "cached_path": str(anchor_path or ""),
            "revision": 1 if anchor_path else 0,
        }
    }


def preview(
    *,
    anchor_revision: int = 1,
    final_systems: list[str] | None = None,
    final_materials: list[str] | None = None,
) -> dict:
    return {
        "id": "preview-ready",
        "layer_name": "trail",
        "preview_path": "D:/tmp/preview.png",
        "preview_kind": "still",
        "status": "approved",
        "anchor_revision": anchor_revision,
        "final_systems": final_systems if final_systems is not None else ["/Game/VFX/NS_Test"],
        "final_materials": final_materials if final_materials is not None else ["/Game/VFX/M_Test.M_Test"],
    }


def effect_preview(
    *,
    final_systems: list[str] | None = None,
    final_materials: list[str] | None = None,
    grid: str = "8x8",
    playback_seconds: float = 2.1,
) -> dict:
    system_path = (final_systems if final_systems is not None else ["/Game/VFX/NS_Test"])[0]
    material_path = (final_materials if final_materials is not None else ["/Game/VFX/M_Test.M_Test"])[0]
    return {
        "id": "effect-preview-ready",
        "preview_path": "D:/tmp/effect-preview.png",
        "preset": "niagara-sandbox",
        "status": "approved",
        "context": {
            "system_path": system_path,
            "material_path": material_path,
            "renderer_path": f"{system_path}.Renderer",
            "grid": grid,
            "playback_seconds": playback_seconds,
            "preview_kind": "still",
            "carrier": "sprite",
        },
    }


def material_delivery(*, approved: bool = True, has_report: bool = True) -> dict:
    return {
        "requested_material_path": "/Game/VFX/M_Test.M_Test",
        "has_delivery_report": has_report,
        "approved_for_reuse": approved,
    }


def material_integration_probe(
    *,
    system_path: str = "/Game/VFX/NS_Test",
    material_path: str = "/Game/VFX/M_Test.M_Test",
    ready: bool = True,
    warnings: int = 0,
    effect: str = "ReadyEffect",
) -> dict:
    errors = 0 if ready else 1
    return {
        "tool": "niagara_material_integration_probe",
        "version": 1,
        "effect": effect,
        "system_path": system_path,
        "expectations": {
            "material_path": material_path,
            "carrier": "sprite",
            "expects_subuv": True,
            "expects_particle_color": True,
        },
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "info": 1,
            "ok": 5 if ready else 2,
        },
        "gate": {
            "integration_ready": bool(ready and errors == 0),
            "requires_triage": bool(errors or warnings),
            "real_system_checked": True,
            "material_preview_is_system_proof": False,
        },
        "findings": [],
    }


def live_report(*, local_file_exists: bool = True, source_policy: str = "required") -> dict:
    return {
        "source_policy": source_policy,
        "local_file": "D:/textures/T_Test.png",
        "local_file_exists": local_file_exists,
        "texture_asset_path": "/Game/VFX/T_Test",
        "texture_asset_exists": True,
        "material_references_target_texture": True,
        "renderer_references_material": True,
    }


def audit_report(
    system_path: str,
    *,
    warnings: list[str] | None = None,
    renderer_classes: list[str] | None = None,
    renderer_materials: list[str] | None = None,
    data_flow: bool = False,
    bounds: bool = True,
    emitter_name: str = "Emitter",
) -> dict:
    return {
        "tool": "niagara_audit",
        "system_path": system_path,
        "system_properties": {
            "FixedBounds": {"text": "(Min=(X=-100,Y=-100,Z=-100),Max=(X=100,Y=100,Z=100))" if bounds else ""},
        },
        "warnings": warnings or [],
        "emitters": [
            {
                "name": emitter_name,
                "id_name": emitter_name,
                "emitter_path": f"{system_path}.{emitter_name}",
                "role": "trail-receiver" if renderer_classes else "generic",
                "parsed": {
                    "renderer_classes": renderer_classes or [],
                    "renderer_materials": renderer_materials or [],
                    "data_interface_bindings": [{"node_name": "ReadSource"}] if data_flow else [],
                    "data_interface_classes": ["ParticleRead"] if data_flow else [],
                    "function_names": ["SampleParticlesFromOtherEmitter"] if data_flow else [],
                    "fixed_bounds": "",
                },
            }
        ],
    }


def attribute_reader_trail_audit_report(system_path: str) -> dict:
    return {
        "tool": "niagara_audit",
        "system_path": system_path,
        "system_properties": {
            "FixedBounds": {"text": "(Min=(X=-100,Y=-100,Z=-100),Max=(X=100,Y=100,Z=100))"},
        },
        "warnings": [],
        "emitters": [
            {
                "name": "Leaders",
                "id_name": "Leaders",
                "emitter_path": f"{system_path}.Leaders",
                "role": "source",
                "roles": ["source"],
                "capabilities": ["attribute-reader-source", "sprite-renderer"],
                "parsed": {
                    "renderer_classes": ["SpriteRendererProperties"],
                    "renderer_materials": [],
                    "data_interface_bindings": [],
                    "data_interface_classes": [],
                    "function_names": ["SpawnBurst_Instantaneous"],
                    "fixed_bounds": "",
                },
            },
            {
                "name": "Followers",
                "id_name": "Followers",
                "emitter_path": f"{system_path}.Followers",
                "role": "trail-receiver",
                "roles": ["trail-receiver", "attribute-reader-receiver"],
                "capabilities": ["ribbon-renderer", "attribute-reader", "inter-emitter-data-flow"],
                "parsed": {
                    "renderer_classes": ["RibbonRendererProperties", "SpriteRendererProperties"],
                    "renderer_materials": ["/Game/VFX/M_Test.M_Test"],
                    "data_interface_bindings": [
                        {
                            "node_name": "NiagaraNodeInput_0",
                            "node_title": "Attribute Reader",
                            "signature_name": "NiagaraDataInterfaceParticleRead",
                            "emitter_binding": "(BindingMode=Other,EmitterName=\"Leaders\")",
                        }
                    ],
                    "data_interface_classes": ["/Script/Niagara.NiagaraDataInterfaceParticleRead"],
                    "function_names": ["SpawnParticlesFromOtherEmitter", "SampleParticlesFromOtherEmitter"],
                    "fixed_bounds": "",
                },
            },
        ],
    }


def write_ready_records(root: Path, *, effect: str = "ReadyCli", audit_warnings: list[str] | None = None) -> dict[str, str]:
    session = root / ".codex" / "session"
    vfx = session / "vfx-delivery"
    anchor_file = root / "anchor.png"
    anchor_file.write_text("anchor", encoding="utf-8")
    source_file = root / "T_Test.png"
    source_file.write_text("texture", encoding="utf-8")
    material_path = "/Game/VFX/M_Test.M_Test"
    system_path = "/Game/VFX/NS_Test"

    save_json(
        vfx / "reference-acceptance" / f"{effect}.json",
        {
            "version": 1,
            "effect_name": effect,
            "anchor_lock": {
                "entry_id": "anchor-ready",
                "implementation_scope": "full effect",
                "scope_confirmed": True,
                "cached_path": str(anchor_file),
                "revision": 1,
            },
            "reviews": [],
        },
    )
    save_json(
        vfx / "preview-approvals" / f"{effect}.json",
        {
            "version": 1,
            "effect_name": effect,
            "reviews": [preview()],
        },
    )
    save_json(
        vfx / "effect-preview-approvals" / f"{effect}.json",
        {
            "version": 1,
            "effect_name": effect,
            "reviews": [
                effect_preview(
                    final_systems=[system_path],
                    final_materials=[material_path],
                )
            ],
        },
    )
    save_json(
        vfx / "live-asset-verify" / effect / "live.json",
        {
            "effect": effect,
            "source_policy": "generated",
            "local_file": str(source_file),
            "local_file_exists": True,
            "texture_asset_path": "/Game/VFX/T_Test",
            "texture_asset_exists": True,
            "material_path": material_path,
            "renderer_path": "/Game/VFX/NS_Test.Renderer",
            "material_references_target_texture": True,
            "renderer_references_material": True,
        },
    )
    save_json(
        vfx / "audits" / "niagara" / effect / "audit.json",
        audit_report(system_path, warnings=audit_warnings),
    )
    save_json(
        vfx / "material-integration-probe" / effect / "niagara-material-integration-probe.json",
        material_integration_probe(system_path=system_path, material_path=material_path, effect=effect),
    )
    save_json(
        session / "material-delivery" / "deliveries" / "M_Test" / "delivery.json",
        {
            "generated_utc": "2026-05-18T00:00:00+00:00",
            "asset": {
                "ue_asset_path": material_path,
                "category": "vfx",
                "role": "material",
                "material_domain": "Surface",
            },
            "delivery_summary": {
                "approved_for_reuse": True,
                "warnings": 0,
                "errors": 0,
            },
        },
    )
    return {
        "effect": effect,
        "source_file": str(source_file),
        "material_path": material_path,
        "system_path": system_path,
    }


def write_visual_reports(root: Path, effect: str, *, pass_reports: bool = True) -> None:
    vfx = root / ".codex" / "session" / "vfx-delivery"
    save_json(
        vfx / "diff-qa" / effect / "trail" / "diff-report.json",
        {
            "effect_name": effect,
            "layer_name": "trail",
            "preview_path": str(root / "preview.png"),
            "metrics": {
                "mean_diff": 12.0 if pass_reports else 90.0,
                "edge_mean_diff": 10.0 if pass_reports else 90.0,
                "mask_delta": 0.05 if pass_reports else 0.8,
            },
        },
    )
    save_json(
        vfx / "design-compare" / effect / "trail.json",
        {
            "effect_name": effect,
            "layer_name": "trail",
            "criteria": [
                {"name": "silhouette", "status": "pass"},
                {"name": "trail_direction", "status": "pass" if pass_reports else "needs-tuning"},
                {"name": "dynamic_rhythm", "status": "pass"},
            ],
        },
    )


def run_main(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def run_tool(tool_main, args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = tool_main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class DeliveryHealthFixtureTests(unittest.TestCase):
    def test_ready_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")

            health = build_delivery_health(
                effect="ReadyEffect",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[live_report()],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test")],
                material_integration_probe_reports=[material_integration_probe()],
                active_assets=["D:/textures/T_Test.png"],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "ready")
        self.assertEqual(health["checks"]["anchor_approval"]["status"], "pass")
        self.assertEqual(health["checks"]["preview_approval"]["status"], "pass")
        self.assertEqual(health["checks"]["effect_preview_approval"]["status"], "pass")
        self.assertEqual(health["checks"]["live_asset_verify"]["status"], "pass")
        self.assertEqual(health["checks"]["niagara_structural_audit"]["status"], "pass")
        self.assertEqual(health["checks"]["material_integration_probe"]["status"], "pass")
        self.assertEqual(health["checks"]["material_delivery_approval"]["status"], "pass")

    def test_missing_anchor_fixture(self) -> None:
        health = build_delivery_health(
            effect="MissingAnchor",
            acceptance=acceptance(None),
            approved_previews=[preview()],
            approved_effect_previews=[],
            live_reports=[],
            final_material_delivery=[material_delivery()],
            niagara_audit_reports=[],
            active_assets=[],
            final_materials=["/Game/VFX/M_Test.M_Test"],
            final_systems=[],
        )

        self.assertEqual(health["overall"], "incomplete")
        self.assertEqual(health["checks"]["anchor_approval"]["status"], "missing")
        self.assertIn("reference_acceptance.py lock", health["checks"]["anchor_approval"]["action_needed"])

    def test_missing_preview_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="MissingPreview",
                acceptance=acceptance(anchor_file),
                approved_previews=[],
                approved_effect_previews=[],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=[],
            )

        self.assertEqual(health["overall"], "incomplete")
        self.assertEqual(health["checks"]["preview_approval"]["status"], "missing")
        self.assertIn("preview_approval.py decide", health["checks"]["preview_approval"]["action_needed"])

    def test_unapproved_material_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="UnapprovedMaterial",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[],
                live_reports=[],
                final_material_delivery=[material_delivery(approved=False)],
                niagara_audit_reports=[],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=[],
            )

        self.assertEqual(health["overall"], "risk")
        self.assertEqual(health["checks"]["material_delivery_approval"]["status"], "risk")

    def test_failed_live_verify_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="FailedLiveVerify",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[],
                live_reports=[live_report(local_file_exists=False)],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[],
                active_assets=["D:/textures/T_Test.png"],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=[],
            )

        self.assertEqual(health["overall"], "risk")
        self.assertEqual(health["checks"]["live_asset_verify"]["status"], "risk")

    def test_ue_only_live_verify_does_not_require_local_file(self) -> None:
        self.assertTrue(live_asset_report_passed(live_report(local_file_exists=False, source_policy="ue-only")))
        self.assertFalse(live_asset_report_passed(live_report(local_file_exists=False, source_policy="generated")))

    def test_niagara_audit_warning_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="AuditWarning",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test", warnings=["renderer missing"])],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "risk")
        self.assertEqual(health["checks"]["niagara_structural_audit"]["status"], "risk")

    def test_preview_must_match_current_final_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="PreviewBinding",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview(final_systems=[], final_materials=[])],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test")],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "risk")
        self.assertEqual(health["checks"]["preview_approval"]["status"], "risk")

    def test_effect_preview_is_required_for_final_system_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="MissingEffectPreview",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test")],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "incomplete")
        self.assertEqual(health["checks"]["effect_preview_approval"]["status"], "missing")
        self.assertIn("effect_preview_approval.py decide", health["checks"]["effect_preview_approval"]["action_needed"])

    def test_effect_preview_must_match_current_final_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="EffectPreviewBinding",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[
                    effect_preview(
                        final_systems=["/Game/VFX/NS_Other"],
                        final_materials=["/Game/VFX/M_Other.M_Other"],
                    )
                ],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test")],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "risk")
        self.assertEqual(health["checks"]["effect_preview_approval"]["status"], "risk")

    def test_material_integration_probe_required_for_final_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="MissingMaterialIntegrationProbe",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test")],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "incomplete")
        self.assertEqual(health["checks"]["material_integration_probe"]["status"], "missing")
        self.assertIn("niagara_material_integration_probe.py", health["checks"]["material_integration_probe"]["action_needed"])

    def test_failing_material_integration_probe_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="FailingMaterialIntegrationProbe",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test")],
                material_integration_probe_reports=[material_integration_probe(ready=False)],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
            )

        self.assertEqual(health["overall"], "risk")
        self.assertEqual(health["checks"]["material_integration_probe"]["status"], "risk")
        self.assertEqual(health["checks"]["material_integration_probe"]["matched_count"], 1)
        self.assertIn("matching probe report", health["checks"]["material_integration_probe"]["detail"])

    def test_niagara_structural_contract_passes_when_evidence_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="ContractReady",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[
                    audit_report(
                        "/Game/VFX/NS_Test",
                        renderer_classes=["RibbonRendererProperties"],
                        renderer_materials=["/Game/VFX/M_Test.M_Test"],
                        data_flow=True,
                        bounds=True,
                    )
                ],
                material_integration_probe_reports=[material_integration_probe()],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
                niagara_contract={
                    "required_renderers": ["Ribbon"],
                    "required_materials": ["/Game/VFX/M_Test.M_Test"],
                    "require_attribute_reader_data_flow": True,
                    "require_bounds": True,
                    "forbid_test_emitters": True,
                },
            )

        self.assertEqual(health["overall"], "ready")
        self.assertEqual(health["checks"]["niagara_structural_audit"]["status"], "pass")

    def test_ribbon_attribute_reader_receiver_satisfies_both_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="CompositeRoleReady",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[
                    audit_report(
                        "/Game/VFX/NS_Test",
                        renderer_classes=["RibbonRendererProperties"],
                        renderer_materials=["/Game/VFX/M_Test.M_Test"],
                        data_flow=True,
                        bounds=True,
                    )
                ],
                material_integration_probe_reports=[material_integration_probe()],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
                niagara_contract={
                    "expected_roles": ["trail-receiver", "attribute-reader-receiver"],
                    "required_renderers": ["Ribbon"],
                    "required_materials": ["/Game/VFX/M_Test.M_Test"],
                    "require_attribute_reader_data_flow": True,
                    "require_bounds": True,
                    "forbid_test_emitters": True,
                },
            )

        self.assertEqual(health["overall"], "ready")
        self.assertEqual(health["checks"]["niagara_structural_audit"]["status"], "pass")

    def test_trail_attribute_reader_contract_accepts_source_and_composite_receiver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="TrailAttributeReaderReady",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[attribute_reader_trail_audit_report("/Game/VFX/NS_Test")],
                material_integration_probe_reports=[material_integration_probe()],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
                niagara_contract={
                    "effect_type": "trail-attribute-reader",
                    "expected_roles": ["source", "attribute-reader-receiver", "trail-receiver"],
                    "required_renderers": ["Ribbon"],
                    "required_materials": ["/Game/VFX/M_Test.M_Test"],
                    "require_attribute_reader_data_flow": True,
                    "require_bounds": True,
                    "forbid_test_emitters": True,
                },
            )

        self.assertEqual(health["overall"], "ready")
        self.assertEqual(health["checks"]["niagara_structural_audit"]["status"], "pass")

    def test_niagara_structural_contract_blocks_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            anchor_file = Path(tmp) / "anchor.png"
            anchor_file.write_text("anchor", encoding="utf-8")
            health = build_delivery_health(
                effect="ContractBlocked",
                acceptance=acceptance(anchor_file),
                approved_previews=[preview()],
                approved_effect_previews=[effect_preview()],
                live_reports=[],
                final_material_delivery=[material_delivery()],
                niagara_audit_reports=[audit_report("/Game/VFX/NS_Test", bounds=False, emitter_name="CodexRendererTest")],
                active_assets=[],
                final_materials=["/Game/VFX/M_Test.M_Test"],
                final_systems=["/Game/VFX/NS_Test"],
                niagara_contract={
                    "required_renderers": ["Ribbon"],
                    "required_materials": ["/Game/VFX/M_Test.M_Test"],
                    "require_attribute_reader_data_flow": True,
                    "require_bounds": True,
                    "forbid_test_emitters": True,
                },
            )

        self.assertEqual(health["overall"], "risk")
        gate = health["checks"]["niagara_structural_audit"]
        self.assertEqual(gate["status"], "risk")
        self.assertGreaterEqual(len(gate["violations"]), 4)


class DeliveryPackageCliFixtureTests(unittest.TestCase):
    def test_cli_writes_manifest_summary_index_and_require_ready_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root)
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--asset",
                    data["source_file"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 0, stderr)
            manifest_path = Path(stdout.strip())
            summary_path = manifest_path.with_name("summary.md")
            index_path = manifest_path.with_name("delivery-index.json")
            self.assertTrue(manifest_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(index_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["delivery_health"]["overall"], "ready")
            self.assertEqual(index["overall"], "ready")
            self.assertEqual(index["niagara_audits"][0]["warning_count"], 0)
            self.assertEqual(manifest["delivery_health"]["checks"]["material_integration_probe"]["status"], "pass")
            self.assertTrue(index["material_integration_probes"][0]["passed"])

    def test_cli_require_ready_fails_for_missing_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="MissingPreviewCli")
            preview_path = root / ".codex" / "session" / "vfx-delivery" / "preview-approvals" / "MissingPreviewCli.json"
            save_json(preview_path, {"version": 1, "effect_name": "MissingPreviewCli", "reviews": []})
            code, _stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 2)
            self.assertIn("not `ready`", stderr)

    def test_cli_require_ready_fails_for_missing_effect_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="MissingEffectPreviewCli")
            effect_preview_path = root / ".codex" / "session" / "vfx-delivery" / "effect-preview-approvals" / "MissingEffectPreviewCli.json"
            save_json(effect_preview_path, {"version": 1, "effect_name": "MissingEffectPreviewCli", "reviews": []})
            code, _stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 2)
            self.assertIn("not `ready`", stderr)

    def test_check_existing_index_without_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="CheckCli")
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                ]
            )
            self.assertEqual(code, 0, stderr)
            index_path = Path(stdout.strip()).with_name("delivery-index.json")
            code, stdout, stderr = run_main(["check", "--index", str(index_path), "--require-ready"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Delivery health: READY", stdout)

    def test_check_existing_manifest_without_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="CheckManifestCli")
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                ]
            )
            self.assertEqual(code, 0, stderr)
            manifest_path = Path(stdout.strip())
            code, stdout, stderr = run_main(["check", "--manifest", str(manifest_path), "--require-ready"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Delivery health: READY", stdout)

    def test_dashboard_and_finalize_consume_ready_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="DashboardFinalizeCli")
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 0, stderr)
            index_path = Path(stdout.strip()).with_name("delivery-index.json")

            dashboard_out = root / "dashboard.json"
            code, _stdout, stderr = run_tool(dashboard_main, ["--root", str(root), "--out", str(dashboard_out), "--markdown"])
            self.assertEqual(code, 0, stderr)
            dashboard = json.loads(dashboard_out.read_text(encoding="utf-8"))
            self.assertEqual(dashboard["counts"].get("ready"), 1)

            code, stdout, stderr = run_tool(finalize_main, ["--root", str(root), "--index", str(index_path)])
            self.assertEqual(code, 0, stderr)
            finalize_path = Path(stdout.strip().splitlines()[-1])
            self.assertTrue(finalize_path.exists())
            finalize = json.loads(finalize_path.read_text(encoding="utf-8"))
            self.assertEqual(finalize["overall"], "ready")

    def test_visual_quality_required_gate_passes_with_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="VisualReadyCli")
            write_visual_reports(root, data["effect"], pass_reports=True)
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                    "--require-visual-qa",
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 0, stderr)
            manifest = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(manifest["delivery_health"]["checks"]["visual_quality"]["status"], "pass")

    def test_visual_quality_required_gate_blocks_missing_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="VisualMissingCli")
            code, _stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                    "--require-visual-qa",
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 2)
            self.assertIn("not `ready`", stderr)

    def test_finalize_dry_run_promote_records_ue_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="FinalizePromoteCli")
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                ]
            )
            self.assertEqual(code, 0, stderr)
            index_path = Path(stdout.strip()).with_name("delivery-index.json")
            code, stdout, stderr = run_tool(
                finalize_main,
                [
                    "--root",
                    str(root),
                    "--index",
                    str(index_path),
                    "--promote-assets",
                    "--promote-root",
                    "/Game/VFX/Final/Test",
                    "--dry-run-promote",
                ],
            )
            self.assertEqual(code, 0, stderr)
            record = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertTrue(record["ue_promote"]["enabled"])
            self.assertTrue(record["ue_promote"]["dry_run"])
            self.assertGreaterEqual(len(record["ue_promote"]["results"]), 2)

    def test_finalize_dry_run_promote_derives_team_template_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="FinalizePromoteTeamCli")
            code, stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                ]
            )
            self.assertEqual(code, 0, stderr)
            index_path = Path(stdout.strip()).with_name("delivery-index.json")
            code, stdout, stderr = run_tool(
                finalize_main,
                [
                    "--root",
                    str(root),
                    "--index",
                    str(index_path),
                    "--promote-assets",
                    "--promote-policy",
                    "studio-project-family-effect",
                    "--promote-base",
                    "/Game/VFX",
                    "--promote-studio",
                    "OpenAI",
                    "--promote-project-name",
                    "UnrealAI",
                    "--promote-effect-family",
                    "Dust",
                    "--promote-effect-name",
                    "FinalizePromoteTeamCli",
                    "--dry-run-promote",
                ],
            )
            self.assertEqual(code, 0, stderr)
            record = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            ue_promote = record["ue_promote"]
            self.assertTrue(ue_promote["enabled"])
            self.assertTrue(ue_promote["dry_run"])
            self.assertEqual(
                ue_promote["promote_root"],
                "/Game/VFX/OpenAI/UnrealAI/Dust/FinalizePromoteTeamCli",
            )
            self.assertEqual(ue_promote["naming"]["effective_policy"], "studio-project-family-effect")
            targets = [item["target"] for item in ue_promote["results"]]
            self.assertTrue(any(target.startswith("/Game/VFX/OpenAI/UnrealAI/Dust/FinalizePromoteTeamCli/") for target in targets))

    def test_dashboard_writes_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = write_ready_records(root, effect="DashboardHtmlCli")
            code, _stdout, stderr = run_main(
                [
                    "--root",
                    str(root),
                    "--effect",
                    data["effect"],
                    "--final-system",
                    data["system_path"],
                    "--final-material",
                    data["material_path"],
                ]
            )
            self.assertEqual(code, 0, stderr)
            dashboard_out = root / "dashboard.json"
            code, _stdout, stderr = run_tool(
                dashboard_main,
                ["--root", str(root), "--out", str(dashboard_out), "--html", "--markdown"],
            )
            self.assertEqual(code, 0, stderr)
            self.assertTrue(dashboard_out.with_suffix(".html").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
