# Closed-Loop Tool Suite

This suite is core to the skill, not optional scaffolding.

## Folder Split

- `tools/`
  User-facing CLIs. These are the commands the skill should invoke directly.
- `scripts/`
  Shared Python implementation, manifest logic, image ops, and Unreal Bridge wrappers.
- `references/`
  Workflow docs, playbooks, and usage notes for the skill itself.

This separation keeps reusable logic out of the CLIs, and keeps skill documentation independent from runtime tooling.

## Tools

### `tools/reference_cache.py`

Purpose:
- cache authoritative design references locally
- separate `active / rejected / debug`
- produce cropped evidence images
- produce larger HQ clarity copies for later anchored generation

Key commands:

```powershell
python tools/reference_cache.py register C:\ref\wing.png --effect WingEcho --label transparent-anchor
python tools/reference_cache.py crop <entry_id> --left 180 --top 90 --right 920 --bottom 760
python tools/reference_cache.py hq <entry_id> --scale 2.0 --sharpen 1.1
python tools/reference_cache.py set-status <entry_id> --status rejected
```

### `tools/reference_acceptance.py`

Purpose:
- record reference approval state
- lock one anchor as the authoritative design image
- keep clarity and authority notes attached to the anchor
- require an explicit implementation scope before the anchor can be considered ready
- act as a hard gate: no locked anchor plus confirmed scope plus durable local cache means implementation should not proceed

### `tools/layer_evidence.py`

Purpose:
- suggest hotspot crops from a reference
- attach a crop and visible evidence to one layer
- push that evidence back into the layer map

### `tools/preview_approval.py`

Purpose:
- gate preview approval before implementation
- track pass / revise / reject state with structured difference notes
- record which anchor revision a preview was approved against
- record the final Niagara system and final material route used to render the preview
- support invalidating old previews to `historical` when the active anchor changes
- delivery health only counts an approved preview when it matches the current anchor revision and current final system/material context

### `tools/effect_preview_approval.py`

Purpose:
- track approval of controlled final effect previews when the task is not anchored to a locked reference image
- record the exact system/material/renderer/grid/playback context for a captured effect preview
- provide a stable approval gate that higher-level tools can check before promoting temporary assets into a formal `/Game/VFX/...` route

### `tools/asset_plan.py`

Purpose:
- derive a first-pass texture/material/Niagara asset plan from the layer map
- attach naming and platform budget guidance before implementation

### `tools/integration_plan.py`

Purpose:
- define notify / socket / owner / user-parameter hookup for runtime integration

### `tools/effect_control_schema.py`

Purpose:
- unify Niagara user variables, runtime component-variable surfaces, and material instance parameters into one control table
- record parameter name, type, default, range, unit, group, runtime-tunable status, and expected driver/owner
- reduce later Blueprint/GAS/Sequencer hookup guesswork by giving every controllable surface one canonical schema row

### `tools/control_preset.py`

Purpose:
- save reusable named control-value presets against an effect control schema
- keep parameter recipes explicit instead of retyping or rediscovering values by memory

### `tools/control_binding_generator.py`

Purpose:
- generate first-pass Blueprint/GAS/AnimNotify/Sequencer binding scaffolds from the control schema plus integration plan
- suggest setter routes and Blueprint variable names/types before hand-written runtime hookup starts

### `tools/control_provenance_check.py`

Purpose:
- verify where each declared control actually comes from
- confirm whether a schema row is backed by live Niagara user-variable evidence, material parameter evidence, or only a placeholder declaration

### `tools/runtime_control_probe.py`

Purpose:
- validate that a runtime Niagara control can be set and read back on a live or transient component route
- optionally capture before/after preview images and report whether the visual output changed enough to count as a real response
- supports ROI-aware visual diff so small center-area changes are not diluted by the full 768x768 preview frame

### `tools/niagara_param_sweep.py`

Purpose:
- sweep a runtime Niagara control across multiple values
- capture one preview per value and compose a comparison sheet for faster control tuning

### `tools/motion_qa.py`

Purpose:
- compare frame sequences over time instead of only still images
- provide first-pass timing/rhythm change evidence for control-driven effect tuning

### `tools/niagara_asset_assistant.py`

Purpose:
- generate reviewable Niagara asset mutation plans
- create systems from templates without losing valid emitter graphs
- add emitters to a system from emitter assets through bridge-backed authoritative editor routes
- duplicate emitters inside a system through bridge-backed authoritative editor routes
- remove emitters from a system cleanly
- toggle emitter enabled state in a system
- create and tune material instances for planned layers
- add a missing Ribbon Renderer to a receiver emitter when `RendererProperties` is empty
- repair existing renderer material bindings when a renderer slot is present
- render the UE Python apply script in dry-run mode
- optionally execute through `unreal-bridge` with `apply-plan --apply`
- read the Niagara system back after writing with `--verify`
- optionally require an existing delivery package to be ready before the apply can count as complete
- optionally run post-apply audit -> delivery package -> ready check with `--auto-delivery-package`

Key commands:

```powershell
python tools/niagara_asset_assistant.py plan-template --effect WingEcho --template-system /Game/VFX/Templates/NS_RibbonTrail_Template --target-system /Game/VFX/WingEcho/NS_WingEcho_Assisted --material-parent /Game/VFX/Masters/MFX_RibbonTrail
python tools/niagara_asset_assistant.py repair-plan --audit .codex/session/vfx-delivery/audits/niagara/.../niagara-audit.json --default-material /Game/VFX/WingEcho/MI_Ribbon
python tools/niagara_asset_assistant.py apply-plan --plan .codex/session/vfx-delivery/ue-mutation-plans/WingEcho/mutation-plan.json --verify
python tools/niagara_asset_assistant.py apply-plan --plan .codex/session/vfx-delivery/ue-mutation-plans/WingEcho/mutation-plan.json --verify --apply
python tools/niagara_asset_assistant.py apply-plan --plan .codex/session/vfx-delivery/ue-mutation-plans/WingEcho/mutation-plan.json --apply --verify --delivery-index .codex/session/vfx-delivery/delivery/WingEcho/delivery-index.json
python tools/niagara_asset_assistant.py apply-plan --plan .codex/session/vfx-delivery/ue-mutation-plans/WingEcho/mutation-plan.json --apply --verify --auto-delivery-package --final-system /Game/VFX/WingEcho/NS_WingEcho --final-material /Game/VFX/WingEcho/MI_WingEcho --effect-type-contract trail
```

Safety notes:
- `apply-plan` is dry-run unless `--apply` is provided.
- The generated UE Python script is saved beside the plan so it can be inspected before execution.
- `apply-plan --apply` now always forces readback verification even if `--verify` was omitted.
- `apply-plan --apply --verify --delivery-index <index>` and `--delivery-effect <effect>` enforce `delivery_health.overall == ready`; if the package is incomplete/risk/blocked, the command exits non-zero and cannot be treated as complete.
- `apply-plan --apply --verify --auto-delivery-package --require-ready-after-package` is the preferred "write then prove" route when the final package context is known.
- Material binding repair only patches an existing renderer `Material=` slot.
- Empty receiver `RendererProperties` can be repaired with `add_ribbon_renderer`; empty source emitters remain source-only unless a separate implementation plan says otherwise.
- Avoid using `NiagaraPythonEmitter.get_modules()` as a generic template-discovery probe in UE 5.7. A real project test crashed NiagaraEditor with a `SharedPointer IsValid()` assertion; use property exports and renderer object readback instead.

### `tools/ue_write_helpers.py`

Purpose:
- provide first-pass write-side Unreal helpers for duplicate, move, MI creation, Niagara template duplication, and system property updates

### `tools/visual_diff_qa.py`

Purpose:
- compare a captured preview against a reference image
- save metrics plus heat / edge / composite outputs

### `tools/gap_diagnosis.py`

Purpose:
- record the visual symptom before tuning
- classify the likely owner layer: reference, texture, material, Niagara, renderer, integration, preview, performance, or unknown
- record evidence, rejected layers, confidence, and the next action
- prevent repeatedly pushing one knob when the real mismatch belongs to another layer
- support historical/blocking statuses such as `historical`, `blocked-missing-anchor-cache`, and `invalidated-by-anchor-switch`

Key commands:

```powershell
python tools/gap_diagnosis.py add --effect WingEcho --layer 翅膀声波残影 --symptom motion --suspect-layer niagara --confidence high --observation "Visible and bright enough, but reads as one folded ribbon instead of 3-5 separated wing arcs." --evidence "Material audit clean; brightness pass improved visibility; shape remains wrong across DesiredAge frames." --rejected-layer material --next-action "Add or repair RibbonID segmentation before more brightness tuning."
python tools/gap_diagnosis.py export-md --effect WingEcho
```

### `tools/live_asset_verify.py`

Purpose:
- verify that a generated texture candidate exists locally
- verify that the corresponding UE texture asset exists
- verify that the live material instance references that texture
- optionally verify that the live renderer references the expected material
- prevent "generated but never actually wired" textures from being treated as implementation state

Source policy:
- `--source-policy generated` or `required` means the local source file must exist
- `--source-policy ue-only` means the UE texture/material/renderer route is enough, for hand-authored or UE-native assets without a local source file
- reports include `effect`, `source_policy`, and `verification_passed` so `delivery_package.py` can consume them without guessing

### `tools/niagara_material_integration_probe.py`

Purpose:
- consume material-side `material_contract.py`, `delivery_packager.py`, and `material_preview.py` evidence
- run or consume a real `niagara_audit.py` report for the final Niagara System
- check the live renderer material binding against the approved material path
- check expected Sprite/Ribbon/Mesh renderer family, SubUV/SubImage evidence, `ParticleColor`, `DynamicParameter`, `RibbonWidth`, sorting/custom sort, and FixedBounds evidence
- keep ownership clear: material preview evidence helps define expectations, but real System/Emitter/Renderer hookup truth belongs here

Key commands:

```powershell
python tools/niagara_material_integration_probe.py --system-path /Game/VFX/WingEcho/NS_WingEcho --material-delivery-package D:/reports/material-delivery-package.json --project C:/UnrealEngineProject/UnrealAI --endpoint 127.0.0.1:57404 --markdown
python tools/niagara_material_integration_probe.py --niagara-audit .codex/session/vfx-delivery/audits/niagara/WingEcho/niagara-audit.json --material-contract D:/reports/material-contract.json --material-path /Game/VFX/WingEcho/MI_Ribbon --carrier ribbon --markdown
```

Workflow notes:
- use this after material delivery evidence exists and before final VFX delivery/finalize
- pass `--strict-unknown` when missing binding evidence should fail instead of only warning
- pass `--fail-on-warning --strict` for automation gates that require every expected binding to be proven
- do not implement this check inside `unreal-material-artist`; that skill owns the material contract and preview evidence, not the live Niagara hookup

### `tools/unrealbridge_upstream_audit.py`

Purpose:
- fetch the latest `TornLux/UnrealBridge` upstream baseline
- compare the upstream baseline against the installed local `unreal-bridge` skill and the live UE project plugin
- treat upstream changes as sync-worthy even when upstream still lacks Niagara support
- preserve local Niagara overlay files instead of letting upstream baseline sync erase them
- custom-merge `UnrealBridge.Build.cs` so upstream additions land while local Niagara module dependencies stay present
- regenerate `bridge_manifest.json` and project `Content/Python/unreal_bridge.py` from the live local plugin surface after sync

Key commands:

```powershell
python tools/unrealbridge_upstream_audit.py --markdown
python tools/unrealbridge_upstream_audit.py --markdown --sync-local
python tools/unrealbridge_upstream_audit.py --markdown --sync-local --bridge-endpoint 127.0.0.1:50343
```

Workflow notes:
- Daily rule: if upstream changed at all, sync the upstream baseline first; do not gate the pull on Niagara capability.
- Local Niagara overlay files stay owned locally:
  - `Source/UnrealBridge/Public/UnrealBridgeNiagaraLibrary.h`
  - `Source/UnrealBridge/Private/UnrealBridgeNiagaraLibrary.cpp`
- Generated bridge surfaces are not copied blindly from upstream:
  - installed skill `scripts/bridge_manifest.json`
  - project plugin `Content/Python/unreal_bridge.py`
- Those generated files should be regenerated from the live local plugin surface after the baseline sync so the final bridge still exposes local Niagara APIs.
- 2026-05-15 bridge-runtime lesson:
  - if `ping` works but `exec` suddenly starts returning `success=false` with `error=\"None\"`, inspect the UE log for Python wrapper failures before blaming Niagara
  - one real cause was a smoke script rebinding top-level `sys`, which polluted stdout/stderr restoration in the old server wrapper
  - after changing `UnrealBridgeServer.cpp`, do a full plugin rebuild or a clean Live Coding compile before judging whether the bridge fix worked

### `tools/delivery_package.py`

Purpose:
- build a delivery manifest from anchors, approvals, plans, tuning logs, and final asset paths
- also consume approved material delivery reports from the sibling `material-delivery` session tree when `--final-material` paths are provided
- surface whether each final material already has an approved material-side delivery report, instead of leaving that truth buried only inside the material skill
- write a compact `Delivery Health` block at the top of `summary.md`
- include the same `delivery_health` object in `manifest.json` so other tools can consume the main gates directly
- write `delivery-index.json` as a compact package-level index for anchors, approved previews, live asset verify reports, final material reports, and audits for `--final-system`
- support `--require-ready` for CI/final packaging: the command exits non-zero when `delivery_health.overall != ready`
- support `check --manifest <path>` and `check --index <path>` to validate an existing package without regenerating it
- consume latest Niagara audit per final system, so historical readbacks do not pollute current package health
- consume `niagara_material_integration_probe.py` reports for final system/material routes, so material-side delivery evidence becomes a real Niagara hookup gate
- consume visual diff and design-compare reports when `--require-visual-qa` is enabled
- support built-in `--effect-type-contract` presets for `trail`, `trail-attribute-reader`, `fire`, `explosion`, and `shield`
- support Niagara structural contract flags:
  - `--require-niagara-renderer`
  - `--require-niagara-material`
  - `--require-attribute-reader-data-flow`
  - `--require-niagara-bounds`
  - `--forbid-test-emitter`

Health gates:
- `Anchor Approval`: locked anchor, confirmed implementation scope, and durable local cached file
- `Preview Approval`: at least one approved preview that matches the current anchor revision and final system/material route
- `Effect Preview Approval`: at least one approved controlled final effect preview that matches the current final system/material route
- `Live Asset Verify`: active generated texture assets are imported into UE and referenced by the live material/renderer route
- `Niagara Structural Audit`: every `--final-system` has a warning-free `niagara_audit.py` report and satisfies the requested renderer/material/data-flow/bounds/test-emitter contract
- `Material Integration Probe`: every final system/material route is covered by a passing `niagara_material_integration_probe.py` report
- `Visual Quality`: when required, visual diff metrics and design-compare checklist criteria must pass for the current effect
- `Material Delivery Approval`: every `--final-material` has a material-side delivery report with `approved_for_reuse=true`

Notes:
- when final Niagara systems are present, `ready` now also requires a matching approved `effect_preview_approval` record for the current final system/material route
- when both final Niagara systems and final materials are present, `ready` now also requires a matching passing `Material Integration Probe`
- `Live Asset Verify`, `Niagara Structural Audit`, `Material Integration Probe`, and `Material Delivery Approval` are shown as `N/A` when their required final route inputs are absent.
- pass `--material-integration-probe <json>` to pin explicit probe evidence; otherwise reports under `.codex/session/vfx-delivery/material-integration-probe/<effect>/` are auto-discovered
- probe reports with warnings block ready by default; pass `--allow-material-integration-warnings` only for deliberate non-final or tolerant package checks
- `live_asset_verify.py` reports should include `effect`; old report files without it are treated as historical and are not pulled into a different effect's health block.
- each health gate includes `action_needed`, and the same action text is shown in `summary.md`
- `delivery-index.json` only includes Niagara audit reports for explicitly passed `--final-system` paths, keeping historical experiments out of package summaries

Offline regression:
- `scripts/test_delivery_package.py` covers ready, missing anchor, missing preview, preview/final-asset binding, material integration probe missing/failing/pass, unapproved material, failed live verify, Niagara audit warnings, Niagara structural contract pass/fail, visual QA pass/fail, `ue-only` source policy behavior, package CLI write flow, `--require-ready`, `check --manifest/--index`, dashboard HTML, dashboard consumption, finalize consumption, and dry-run UE promote mapping

UE smoke:
- 2026-05-18 verified `live_asset_verify.py --source-policy ue-only` against live UE 5.8 project `C:/UnrealEngineProject/UnrealAI`
- Smoke report: `.codex/session/vfx-delivery/live-asset-verify/ue-only-smoke/live-asset-verify.json`
- Result: `verification_passed=true` with no local source file, because the UE texture asset, material texture parameter, and renderer material chain all resolved
- `tools/ue_smoke.py` is the optional automated smoke entry. If UE is unavailable it writes a `status=blocked` report and returns success unless `--require-ue` is set; if a texture/material/renderer route is supplied, it runs the same live asset route check with `--source-policy ue-only` by default.

### `tools/flipbook_builder.py`

Purpose:
- recommend a UE/Niagara-friendly flipbook grid from a source video
- optionally extract sampled video frames and compose a PNG atlas plus per-frame PNGs
- support both auto recommendation and explicit artist-defined grids such as `4x4`, `8x4`, or `8x8`
- snap generated atlas width and height to the nearest power of two by default, for example raw `2160x4090` becomes `2048x4096`
- write `flipbook-manifest.json` with SubUV columns/rows, frame count, cell size, atlas size, sample timestamps, and suggested play rate

Key commands:

```powershell
python tools/flipbook_builder.py recommend C:\VFX\fire.mp4
python tools/flipbook_builder.py recommend C:\VFX\fire.mp4 --start 00:01.250 --end 00:03.000
python tools/flipbook_builder.py recommend --no-probe --source-size 1024x1024 --duration 2.0 --source-fps 30 --target-fps 12
python tools/flipbook_builder.py build C:\VFX\fire.mp4 --effect FireBurst --grid auto --target-fps 12
python tools/flipbook_builder.py build C:\VFX\fire.mp4 --effect FireBurst --grid 8x8 --cell-size 256x256 --frames 64 --start 1.25 --end 3.0
python tools/flipbook_builder.py build C:\VFX\dust.mov --effect Dust --grid 10x10 --cell-size 216x409 --frames 100
```

Workflow notes:
- `recommend` requires `ffprobe` unless manual metadata is supplied with `--no-probe --source-size --duration --source-fps`.
- `build` requires `ffmpeg` for frame extraction and Pillow for image composition.
- executable discovery order is explicit `--ffmpeg/--ffprobe`, project-local `Tools/FFmpeg` or `tools/ffmpeg`, PATH, then optional Python `imageio-ffmpeg` for `ffmpeg` only.
- for portable FFmpeg on Windows, either place `bin\ffmpeg.exe` and `bin\ffprobe.exe` under project-local `Tools\FFmpeg`, or pass `--ffmpeg C:\Tools\ffmpeg\bin\ffmpeg.exe`; `recommend` will also look for sibling `ffprobe.exe` in that folder.
- if FFmpeg is present only as an archive such as `.tar.xz`, the tool reports that no executable was found instead of silently falling back.
- if `ffmpeg` or `ffprobe` runs and fails, the tool reports the executable path, command, exit code, and stderr/stdout tail so the real codec/path/probe failure is visible.
- `--start` and `--end` are shared by `recommend` and `build`; when omitted the tool uses the full video.
- time arguments accept seconds (`1.25`), `MM:SS` (`00:03.500`), or `HH:MM:SS` (`00:00:03.500`).
- auto grid recommendation is based on the selected clip duration, not always the full source video.
- atlas output defaults to `--atlas-size-mode nearest-power-of-two`, snapping each axis independently to the closest power of two. Use `--atlas-size-mode raw` only for debugging or comparison.
- the manifest records both the final atlas size and raw pre-snap size through `atlas.raw_width`, `atlas.raw_height`, `atlas.size_mode`, `atlas.power_of_two`, and `atlas.snapped_from`.
- default output is `.codex/session/vfx-delivery/flipbooks/<effect>/<run-id>/`.
- the atlas uses row-major order: frame 0 at top-left, then left-to-right, top-to-bottom.
- for Niagara Sprite Renderer SubUV setup, use `ue_notes.sub_uv_columns`, `ue_notes.sub_uv_rows`, and `ue_notes.suggested_play_rate_fps` from the manifest.

### `tools/flipbook_ue_pipeline.py`

Purpose:
- turn a local flipbook atlas into a UE texture asset plus a ready-to-preview SubUV material in one command
- bridge the current gap between atlas generation and UE material hookup
- reuse local UnrealBridge transport plus existing material-skill audit/fix tools while hiding the multi-step glue
- optionally render a sprite preview with the requested SubUV grid
- optionally duplicate and patch a Niagara sprite system, bind the new material, add `SubUVAnimation`, set playback-driving stack inputs, and run verification reports
- optionally promote the generated texture/material/Niagara route from `/Game/CodexTemp/...` into a target `/Game/VFX/...` folder, with duplicate-or-move behavior plus post-promote verification
- optionally capture a controlled final effect preview and create a pending approval record for that exact system/material/grid context
- optionally gate real promote on an already-approved effect preview record for the same context

Key command:

```powershell
python tools/flipbook_ue_pipeline.py D:\atlas\flipbook_atlas.png --grid 8x8 --effect Dust36 --project C:\UnrealEngineProject\UnrealAI --endpoint 127.0.0.1:56233 --preview --markdown
python tools/flipbook_ue_pipeline.py D:\atlas\flipbook_atlas.png --grid 8x8 --effect Dust36 --project C:\UnrealEngineProject\UnrealAI --endpoint 127.0.0.1:56233 --preview --niagara-hookup --markdown
python tools/flipbook_ue_pipeline.py D:\atlas\flipbook_atlas.png --grid 8x8 --effect Dust36 --project C:\UnrealEngineProject\UnrealAI --endpoint 127.0.0.1:56233 --preview --niagara-hookup --effect-preview --approval-create-pending --markdown
python tools/flipbook_ue_pipeline.py D:\atlas\flipbook_atlas.png --grid 8x8 --effect Dust36 --project C:\UnrealEngineProject\UnrealAI --endpoint 127.0.0.1:56233 --preview --niagara-hookup --promote --promote-policy vfx-effect --promote-group CodexSmoke --promote-effect-name Dust36 --promote-mode duplicate --markdown
python tools/flipbook_ue_pipeline.py D:\atlas\flipbook_atlas.png --grid 8x8 --effect Dust36 --project C:\UnrealEngineProject\UnrealAI --endpoint 127.0.0.1:56233 --preview --niagara-hookup --promote --promote-policy studio-project-family-effect --promote-studio OpenAI --promote-project-name UnrealAI --promote-effect-family Dust --promote-effect-name Dust36 --promote-mode duplicate --markdown
```

Workflow notes:
- default asset destinations are derived under `/Game/CodexTemp/<Effect>/Textures/` and `/Game/CodexTemp/<Effect>/Materials/`.
- when `--niagara-hookup` is enabled, default Niagara destination is `/Game/CodexTemp/<Effect>/Niagara/NS_<Effect>_SubUV`.
- texture import now prefers the formal `UnrealBridgeAssetLibrary.ImportTexture2DFromFile` route. Under the hood that bridge API currently still uses UE's import task pipeline because official `TextureTools` does not expose a usable import verb in this build.
- the tool then runs `texture_import_fix.py` and `material_audit.py` automatically and records their report paths.
- material creation is intentionally hybrid:
  - official `MaterialTools.create` creates the asset
  - local guid-aware material graph ops wire `TextureSampleParameterSubUV`, `ParticleColor`, and the output chain
- optional preview uses a temporary Niagara sprite harness with the requested `SubImageSize`, so the screenshot checks the real SubUV grid rather than only a mesh/shaderball surrogate.
- preview Niagara now defaults to a transient `/Engine/Transient...` duplicate instead of writing a `/Game/CodexTemp/MaterialPreview/...` content asset
- transient preview now uses one stable object per carrier/template pair, for example `/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke`
- explicit maintenance is now available through sibling material tooling:
  - `python ..\unreal-material-artist\tools\material_preview.py transient list ...`
  - `python ..\unreal-material-artist\tools\material_preview.py transient recycle ...`
  - `python ..\unreal-material-artist\tools\material_preview.py transient recycle-all ...`
  - `python ..\unreal-material-artist\tools\material_preview.py transient prune [--apply] ...`
- preview success now includes cleanup truth; if the route falls back to a content asset and cleanup fails, the image may still render but the preview should not be treated as fully passed
- Niagara hookup is also intentionally hybrid:
  - duplicate/save uses official `AssetTools`
  - renderer patching uses direct UE Python object property writes
  - `SubUVAnimation` / stack input writes use `UnrealBridgeNiagaraLibrary` official external-edit wrappers
  - verification uses `live_asset_verify.py`, `niagara_audit.py`, and compile-state readback
- if the atlas sits beside a `flipbook-manifest.json`, the tool auto-inherits playback seconds from `clip.duration_seconds` unless `--niagara-playback-seconds` overrides it.
- `--effect-preview` captures a controlled preview of the active Niagara system through `controlled_preview.py niagara`.
- `--approval-create-pending` writes a pending review into `effect-preview-approvals/<effect>.json` for the exact system/material/grid/playback context.
- real `--promote` now expects an already-approved effect preview by default; use `tools/effect_preview_approval.py decide --effect <effect> --review-id <id> --status approved` after visual review, or explicitly bypass with `--allow-promote-without-approved-preview`.
- texture import route is reported explicitly in the pipeline report:
  - `bridge-uassetlibrary` = direct formal `UnrealBridgeAssetLibrary` API
  - `bridge-uassetlibrary-reflection` = same formal API reached through reflection when the Python binding table has not refreshed yet
  - `plugin-python-helper` = last-resort plugin Python fallback
- promote stage supports:
  - `--promote` to enable promote
  - `--promote-policy vfx-effect` as the default formal naming rule
  - `--promote-base /Game/VFX`, `--promote-group CodexSmoke`, `--promote-effect-name Dust36` to derive `/Game/VFX/CodexSmoke/Dust36`
  - `--promote-policy studio-project-family-effect` for a more production-shaped template, for example `--promote-studio OpenAI --promote-project-name UnrealAI --promote-effect-family Dust --promote-effect-name Dust36` -> `/Game/VFX/OpenAI/UnrealAI/Dust/Dust36`
  - `--promote-root /Game/VFX/MyEffect` still overrides policy-derived roots when you need an explicit destination
  - `--promote-mode duplicate|move`
  - `--promote-dry-run` for path planning without mutation
  - duplicate mode automatically repatches the promoted material's flipbook texture parameter and the promoted Niagara renderer material binding before verification
  - markdown and JSON reports now show both the requested policy and the effective policy, so manual-root overrides are easy to spot during review

### `tools/delivery_chain_smoke.py`

Purpose:
- run a real effect delivery chain instead of only fixture tests
- sequence Niagara audit, optional live asset verify, delivery package/check, dashboard generation, and optional finalize
- keep package health honest: the tool execution can pass while `delivery_overall` is still `risk` or `incomplete`
- write `.codex/session/vfx-delivery/chain-smoke/<effect>/delivery-chain-smoke.json`

Key command:

```powershell
python tools/delivery_chain_smoke.py --effect WingEcho --final-system /Game/VFX/.../NS_WingEcho --final-material /Game/VFX/.../MI_WingEcho --texture-asset-path /Game/VFX/.../T_Flow --material-path /Game/VFX/.../MI_WingEcho --renderer-path /Game/VFX/...:Emitter.Renderer --source-policy ue-only --effect-type-contract trail-attribute-reader --html-dashboard --markdown
```

### `tools/delivery_dashboard.py`

Purpose:
- scan every `delivery-index.json` under the active root
- summarize ready / risk / incomplete / blocked package counts
- list open gates and action-needed text for daily review, CI dashboards, or batch QA
- optionally write `delivery-dashboard.html` with package cards and visible action-needed text

### `tools/delivery_finalize.py`

Purpose:
- promote a VFX package into the final delivery record only when `delivery-index.json` is ready
- run the same `delivery_package.py check --index --require-ready` logic before writing `.codex/session/vfx-delivery/finalized/<effect>/finalize.json`
- record final systems, final materials, source manifest, source summary, and notes for handoff
- optionally promote UE assets with `--promote-assets`, `--promote-root`, `--promote-map`, `--promote-mode move|duplicate`, and `--dry-run-promote`
- `delivery_finalize.py` can also derive a formal promote root from the same shared naming policies as `flipbook_ue_pipeline.py`, for example `--promote-policy studio-project-family-effect --promote-studio OpenAI --promote-project-name UnrealAI --promote-effect-family Dust --promote-effect-name Dust36`
- because `delivery_finalize.py` reuses `delivery_package.py check --require-ready`, it now naturally inherits the final `effect_preview_approval` gate too
- use dry-run promote first; real promote touches UE assets and should only run after the package is ready

### `tools/learning_loop.py`

Purpose:
- generate reusable lessons from approvals, anchor locks, and tuning history
- keep manual success / failure / reuse rules with the effect record
- consume the latest or explicitly provided `delivery-index.json` during `summarize`
- write delivery health and open gates into the learning summary so delivery-index becomes part of the skill ecosystem, not just an output file

### `tools/visual_layer_map.py`

Purpose:
- record each visual layer's evidence
- map it to its UE carrier
- record the required textures, material route, Niagara route, and self-test checks

Key commands:

```powershell
python tools/visual_layer_map.py init --effect WingEcho --anchor-reference-id ref_001
python tools/visual_layer_map.py add-layer --effect WingEcho --name 翅膀声波残影 --field ue_carrier.primary=RibbonTrail --field evidence.motion_cue=wing-peak-burst
python tools/visual_layer_map.py export-md --effect WingEcho
```

### `tools/niagara_audit.py`

Purpose:
- inspect Niagara system emitter handles
- inspect likely emitter roles
- preserve composite emitter roles and capabilities, for example a Ribbon receiver that is also an Attribute Reader receiver
- inspect renderer types, material bindings, sim target, bounds, and event-handler presence
- emit structural warnings before visual tuning
- feed `niagara_material_integration_probe.py` when the question is specifically whether a material contract is truly satisfied by the live Niagara route

### `tools/controlled_preview.py`

Purpose:
- create deterministic preview captures that do not rely on editor UI screenshots
- support material previews, fixed-camera actor captures, and first-pass Niagara captures

### `tools/design_compare_checklist.py`

Purpose:
- generate the design-comparison checklist for a layer
- track pass / fail / needs-tuning decisions for silhouette, brightness, density, width, trail direction, echo spacing, and dynamic rhythm

### `tools/asset_cleanup.py`

Purpose:
- safely report stale local artifacts
- optionally delete tagged Unreal preview actors and disposable local artifacts after a report is reviewed
- when `report --effect <name>` is used, read the latest `delivery-index.json` and include a `delivery_guard` summary
- surface open delivery gates during cleanup so cleanup/finalization does not accidentally hide an incomplete package
- can scan UE temp Niagara assets such as `/Game/CodexTemp/MaterialPreview/NS_CodexPreview_*` and smoke-only Niagara outputs
- apply reports now distinguish `removed` from `failed`, so cleanup does not silently claim success when UE keeps a temp asset alive

### `tools/parameter_tuning_log.py`

Purpose:
- record what was tuned
- record why it was tuned
- record which visual gap it was trying to close

## Default Data Location

When `--root` is omitted, tools auto-detect a project root and write under:

```text
<project>/.codex/session/vfx-delivery/
```

This keeps cached references, audits, previews, cleanup reports, and tuning logs tied to the active Unreal project instead of polluting the skill repo.

## Recommended Order

1. `reference_cache.py`
2. `reference_acceptance.py`
3. `layer_evidence.py`
4. `visual_layer_map.py`
5. `controlled_preview.py`
6. `preview_approval.py`
7. `asset_plan.py`
8. `integration_plan.py`
9. `niagara_audit.py`
10. `niagara_material_integration_probe.py`
11. `niagara_asset_assistant.py`
12. `ue_write_helpers.py`
13. `visual_diff_qa.py`
14. `design_compare_checklist.py`
15. `gap_diagnosis.py`
16. `parameter_tuning_log.py`
17. `delivery_package.py`
18. `delivery_chain_smoke.py`
19. `delivery_dashboard.py`
20. `delivery_finalize.py`
21. `ue_smoke.py`
22. `flipbook_builder.py`
23. `learning_loop.py`
24. `asset_cleanup.py`
25. `unrealbridge_upstream_audit.py`

That order matches the closed loop:

reference anchor -> acceptance gate -> visible evidence -> carrier-aware preview -> preview approval -> plan -> integration -> Niagara audit -> material integration probe -> mutation plan -> write-side implementation -> diff QA -> design compare -> gap diagnosis -> tuning -> delivery -> chain smoke -> dashboard/finalize/smoke -> learning -> cleanup.

Material graph auditing moved to `D:/Skills/skills/unreal-material-artist/tools/material_audit.py`; use it before Niagara tuning when renderer materials are part of the risk.
