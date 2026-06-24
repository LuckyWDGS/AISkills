from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vfx_delivery.effect_preview_approval import build_context, context_key
from vfx_delivery.flipbook_ue_pipeline import (
    asset_token,
    adjacent_manifest_path,
    derive_default_asset_paths,
    derive_default_niagara_system_path,
    derive_default_promote_paths,
    derive_formal_promote_root,
    load_adjacent_manifest,
    manifest_grid,
    manifest_playback_seconds,
    package_to_object_ref,
    resolve_promote_root,
)
from vfx_delivery.promote_naming import resolve_promote_details


class FlipbookUEPipelineTests(unittest.TestCase):
    def test_asset_token_normalizes_and_avoids_leading_digit(self) -> None:
        self.assertEqual(asset_token("Dust 22 16x16"), "Dust_22_16x16")
        self.assertEqual(asset_token("22"), "A_22")
        self.assertEqual(asset_token(""), "Asset")

    def test_package_to_object_ref_adds_leaf_name(self) -> None:
        self.assertEqual(
            package_to_object_ref("/Game/CodexTemp/Dust36/Textures/T_Dust36_Atlas"),
            "/Game/CodexTemp/Dust36/Textures/T_Dust36_Atlas.T_Dust36_Atlas",
        )
        self.assertEqual(
            package_to_object_ref("/Game/CodexTemp/Dust36/Textures/T_Dust36_Atlas.T_Dust36_Atlas"),
            "/Game/CodexTemp/Dust36/Textures/T_Dust36_Atlas.T_Dust36_Atlas",
        )

    def test_derive_default_asset_paths(self) -> None:
        texture_path, material_path = derive_default_asset_paths("Dust 36 8x8")
        self.assertEqual(texture_path, "/Game/CodexTemp/Dust_36_8x8/Textures/T_Dust_36_8x8_Atlas")
        self.assertEqual(material_path, "/Game/CodexTemp/Dust_36_8x8/Materials/M_Dust_36_8x8_SubUV")

    def test_derive_default_niagara_system_path(self) -> None:
        self.assertEqual(
            derive_default_niagara_system_path("Dust 36 8x8"),
            "/Game/CodexTemp/Dust_36_8x8/Niagara/NS_Dust_36_8x8_SubUV",
        )

    def test_derive_default_promote_paths(self) -> None:
        paths = derive_default_promote_paths(
            promote_root="/Game/VFX/Dust36",
            texture_asset_path="/Game/CodexTemp/Dust36/Textures/T_Dust36_Atlas",
            material_asset_path="/Game/CodexTemp/Dust36/Materials/M_Dust36_SubUV",
            niagara_system_path="/Game/CodexTemp/Dust36/Niagara/NS_Dust36_SubUV",
        )
        self.assertEqual(paths["texture"], "/Game/VFX/Dust36/Textures/T_Dust36_Atlas")
        self.assertEqual(paths["material"], "/Game/VFX/Dust36/Materials/M_Dust36_SubUV")
        self.assertEqual(paths["niagara"], "/Game/VFX/Dust36/Niagara/NS_Dust36_SubUV")

    def test_derive_formal_promote_root(self) -> None:
        self.assertEqual(
            derive_formal_promote_root(
                promote_base="/Game/VFX",
                promote_policy="vfx-effect",
                promote_group="Golden Goose",
                promote_effect_name="Wing Echo",
            ),
            "/Game/VFX/Golden_Goose/Wing_Echo",
        )

    def test_derive_formal_promote_root_studio_project_family_effect(self) -> None:
        self.assertEqual(
            derive_formal_promote_root(
                promote_base="/Game/VFX",
                promote_policy="studio-project-family-effect",
                promote_studio="Studio Alpha",
                promote_project_name="Golden Goose",
                promote_effect_family="Dust Bursts",
                promote_effect_name="Wing Echo",
            ),
            "/Game/VFX/Studio_Alpha/Golden_Goose/Dust_Bursts/Wing_Echo",
        )

    def test_resolve_promote_root_prefers_explicit_root(self) -> None:
        self.assertEqual(
            resolve_promote_root(
                effect="Dust36",
                explicit_root="/Game/VFX/Manual/Path",
                promote_policy="vfx-effect",
                promote_base="/Game/VFX",
                promote_group="Codex",
                promote_effect_name="Dust36",
            ),
            "/Game/VFX/Manual/Path",
        )

    def test_resolve_promote_root_vfx_effect_policy(self) -> None:
        self.assertEqual(
            resolve_promote_root(
                effect="Dust36",
                explicit_root="",
                promote_policy="vfx-effect",
                promote_base="/Game/VFX",
                promote_group="CodexSmoke",
                promote_effect_name="Dust36_Final",
            ),
            "/Game/VFX/CodexSmoke/Dust36_Final",
        )

    def test_resolve_promote_root_studio_project_family_effect_policy(self) -> None:
        self.assertEqual(
            resolve_promote_root(
                effect="Dust36",
                explicit_root="",
                promote_policy="studio-project-family-effect",
                promote_base="/Game/VFX",
                promote_studio="OpenAI",
                promote_project_name="UnrealAI",
                promote_effect_family="Dust",
                promote_effect_name="Dust36_Final",
            ),
            "/Game/VFX/OpenAI/UnrealAI/Dust/Dust36_Final",
        )

    def test_resolve_promote_details_tracks_requested_and_effective_policy(self) -> None:
        details = resolve_promote_details(
            effect="Dust36",
            explicit_root="/Game/VFX/Manual/Path",
            promote_policy="studio-project-family-effect",
            promote_base="/Game/VFX",
            promote_group="Ignored",
            promote_effect_name="Dust36_Final",
            promote_studio="OpenAI",
            promote_project_name="UnrealAI",
            promote_effect_family="Dust",
        )
        self.assertEqual(details["requested_policy"], "studio-project-family-effect")
        self.assertEqual(details["effective_policy"], "manual-root")
        self.assertEqual(details["promote_root"], "/Game/VFX/Manual/Path")
        self.assertEqual(details["segments"], [])

    def test_adjacent_manifest_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            atlas = root / "flipbook_atlas.png"
            atlas.write_text("atlas", encoding="utf-8")
            manifest = root / "flipbook-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "clip": {"duration_seconds": 2.1},
                        "grid": {"columns": 8, "rows": 8},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertEqual(adjacent_manifest_path(atlas), manifest)
            payload = load_adjacent_manifest(atlas)
            self.assertEqual(manifest_playback_seconds(payload), 2.1)
            self.assertEqual(manifest_grid(payload), "8x8")

    def test_effect_preview_context_key_is_stable(self) -> None:
        a = build_context(
            system_path="/Game/A/NS_Test",
            material_path="/Game/A/M_Test",
            renderer_path="/Game/A/NS_Test:Renderer",
            grid="8x8",
            playback_seconds=2.1,
            preview_kind="still",
            carrier="sprite",
        )
        b = build_context(
            system_path="/Game/A/NS_Test",
            material_path="/Game/A/M_Test",
            renderer_path="/Game/A/NS_Test:Renderer",
            grid="8x8",
            playback_seconds=2.1,
            preview_kind="still",
            carrier="sprite",
        )
        c = build_context(
            system_path="/Game/A/NS_Test",
            material_path="/Game/A/M_Test_2",
            renderer_path="/Game/A/NS_Test:Renderer",
            grid="8x8",
            playback_seconds=2.1,
            preview_kind="still",
            carrier="sprite",
        )
        self.assertEqual(context_key(a), context_key(b))
        self.assertNotEqual(context_key(a), context_key(c))


if __name__ == "__main__":
    unittest.main()
