---
name: vfx-flipbook-generator
description: Plan, generate, extend, repair and pack VFX flipbook atlases for smoke, dust, powder, fire, flame, embers, sparks, explosions, mist, clouds and other sprite or SubUV effects. Use when the user asks for a flipbook, sequence atlas, SubUV atlas or sprite sheet; when short alpha videos, sparse footage, still references or text direction must become a production-ready grid; when the requested grid has more cells than the usable source frames; or when generated smoke, fire or particle frames need assembling into a power-of-two atlas.
---

# VFX Flipbook Generator

Atlas generation, FFmpeg extraction, alpha QA, packing and manifests run
locally: every tool in this skill is `local` and needs no editor. Only the
final [Unreal handoff](#unreal-handoff) touches UE.

## When to use

Use this skill when the user wants a flipbook atlas rather than a single
concept image:

- choose between source footage, hybrid generation and full generation;
- gather references and generate frames when source material is short or weak;
- assemble frames into a power-of-two atlas ready for SubUV use;
- scaffold a job pack from a short request such as `smoke 8x8 6s`;
- turn a job into a per-frame batch plan and run it phase by phase with anchor
  approval gates;
- gate Unreal delivery with a readiness check.

Resolve script paths relative to this skill directory. Media and job paths in
the examples are placeholders. Scripts need Python 3.10+.

## Workflow

1. **Quantify the source before committing to a grid.**
   - For a short request such as `smoke 8x8 6s`, scaffold a job pack first:

     ```powershell
     python tools/flipbook_job_scaffold.py "smoke 8x8 6s"
     ```

     It writes route advice, search queries, anchor prompts, an output folder
     plan and a packing command template.
   - For a video, measure usable clip duration, fps and approximate sample
     count, then ask the route advisor:

     ```powershell
     python tools/flipbook_route_advisor.py --grid 8x8 --effect dust --clip-duration 6.2 --source-fps 23.976 --markdown
     ```

   - Treat the route as the first decision, open to revision.

2. **Use the matching route.**
   - `direct-extract`: the source has enough samples for the grid. Use
     `tools/flipbook_builder.py`. It finds FFmpeg under `tools/ffmpeg` (not
     committed; install per machine), then on `PATH`, then the
     `imageio-ffmpeg` package. On a new machine run
     `winget install Gyan.FFmpeg` or unpack a build into
     `tools/ffmpeg/<build>/bin`. Keep `--fit contain` (scale and pad) unless
     cropping is wanted (`cover`).
   - `hybrid`: the source has good motion but thin temporal coverage. Keep the
     best real motion, generate missing states or bridge frames with the
     system image generator, and pack with `frame_atlas_packer.py`.
   - `full-generated`: little or no usable footage, or a custom effect that
     source reuse would fight. Gather references, generate a consistent frame
     family, then pack.

3. **Search when reference coverage is weak or the user asks.**
   - Search for motion language, shape breakup, density, timing and
     silhouette: `falling dust alpha`, `smoke plume reference`,
     `torch flame side view`, `embers burst reference`.
   - References inform the work. Stock atlases are not ripped or presented as
     new work.
   - Record the useful queries and what each reference contributed.

4. **Keep invariants locked while generating.**
   - One canvas size, one camera angle, one background policy (black for
     luminance-style cards, transparent when the route supports it), the
     subject centered at a stable scale, one effect family.
   - Generate at `2048x2048` or `4096x4096` for final atlas sources. Use
     `1024x1024` for chat previews, quick reviews, mobile-only assets or an
     explicit low-budget derivative. When the provider cannot generate 2K/4K,
     keep the best raw output, record the limit, and make an upscaled
     derivative only with the user's acceptance.
   - Generate 4-8 anchor states, review them, then fill the family. After a
     phase anchor is accepted, fill that phase by image-reference edit before
     falling back to text generation.
   - Before demanding strict continuity, read
     [sequence-boundaries.md](references/sequence-boundaries.md): a
     randomizable sprite set may serve the effect better.

5. **Solve frame scarcity at the source.**
   - A thin source stays thin when Niagara stretches time.
   - Smoke, dust, powder and mist: keep internal motion near source timing and
     let Niagara extend life with size, alpha, drag and support layers.
   - Flame and hero fire: treat low coverage as a generation problem early,
     because slow playback exposes stepping.

6. **Pack frames into an atlas.**
   - Source video: `flipbook_builder.py`, with `--fit contain` when the full
     frame must be kept.
   - Frame folders, generated families or curated PNGs:

     ```powershell
     python tools/frame_atlas_packer.py D:/path/to/frames --grid 8x8 --cell-size 256x256 --out-dir D:/path/to/out --atlas-name smoke_flipbook.png
     ```

   - Output is power-of-two by default. For Unreal delivery use `2048x2048` or
     `4096x4096` with exact grid divisibility, and downscale from that source
     for smaller variants.
   - When padding to power-of-two, expand and center every cell inside its
     final UV tile and record final and source cell dimensions. Padding only
     the outside of the atlas shifts SubUV boundaries.
   - Job scaffolds require power-of-two row and column counts. For 144 source
     frames use `16x16 --frames 144` with playback indices `0..143` and leave
     the other 112 cells unused. Packers reject excess frames. An exact
     `12x12` or `10x10` grid needs an explicit `--atlas-size-mode raw` NPOT
     plan and platform validation.

7. **Run a QC pass before delivery.**
   - No accidental blank rows or columns; consistent alpha and background
     policy; limited frame-to-frame scale drift; transparent padding that is
     expected rather than a sign to switch from `contain` to `cover`.
   - For Unreal, report grid columns and rows, frame count, final atlas
     dimensions, exact cell dimensions or a divisibility warning, raw pre-snap
     dimensions, suggested playback fps, frame order, start and end frame,
     alpha policy and blend-mode recommendation, then run the readiness gate:

     ```powershell
     python tools/ue_flipbook_readiness.py D:/path/to/atlas.png --manifest D:/path/to/flipbook-manifest.json --mode both --alpha-policy auto
     ```

   - For a folder of candidates, build a selection catalog:

     ```powershell
     python tools/flipbook_asset_catalog.py D:/path/to/atlas-folder --out D:/path/to/atlas-folder/atlas-catalog.md --json-out D:/path/to/atlas-folder/atlas-catalog.json
     ```

8. **Hand off downstream.**
   - `niagara-vfx-artist` for Niagara hookup, SubUV setup and renderer
     validation.
   - `unreal-material-artist` for the material route, blend mode, alpha
     behavior and flipbook texture strategy.
   - The system image generator is the default for generated frames;
     `cm-imagegen` when the user wants the local CLI route or local automation.

## Commands

| Task | Command |
|---|---|
| Source video to atlas | `python tools/flipbook_builder.py build D:/clip.mov --start 0.2 --end 6.5 --grid 16x16 --frames 144 --cell-size 128x128 --fit contain --background transparent --atlas-size-mode pad-to-power-of-two` |
| Route decision | `python tools/flipbook_route_advisor.py --grid 8x8 --effect smoke --clip-duration 3.5 --source-fps 25 --markdown` |
| Job scaffold | `python tools/flipbook_job_scaffold.py "smoke 8x8 6s" --out-root D:/flipbook-jobs` |
| Per-frame plan | `python tools/flipbook_batch_plan.py <job>/job-spec.json --prompt-suffix "gravity-driven downward motion, no environment"` |
| Phase status and run | `python tools/flipbook_batch_runner.py status <job>/frame-plan.json`, then `run` |
| Import an approved anchor | `python tools/flipbook_batch_runner.py import-frame <job>/frame-plan.json --frame 1 --path "D:/generated/frame_001.png" --approve-anchor` |
| Pack generated frames | `python tools/frame_atlas_packer.py D:/frames/smoke_a --grid 8x8 --cell-size 256x256 --fit contain --background transparent --atlas-size-mode pad-to-power-of-two --out-dir D:/atlas_out --atlas-name smoke_8x8.png` |
| Readiness gate | `python tools/ue_flipbook_readiness.py D:/atlas_out/smoke_8x8.png --manifest D:/atlas_out/flipbook-manifest.json --mode both --alpha-policy auto` |
| Candidate catalog | `python tools/flipbook_asset_catalog.py D:/atlas_out --out D:/atlas_out/atlas-catalog.md --json-out D:/atlas_out/atlas-catalog.json` |
| 2K/4K derivatives | `python tools/flipbook_atlas_resizer.py D:/atlas_out/fx_sheet_4x4_1024.png --alpha-path D:/atlas_out/fx_sheet_alpha_4x4_1024.png --grid 4x4 --targets 2048 4096 --out-dir D:/atlas_out/highres` |

## Unreal handoff

> **Scope.** This bundle targets UE 5.8 (verified on UE 5.8.4). For a UE 5.9
> editor the user links `skills/ue5.9/` instead.

Follow the [shared conventions](../unreal-engine-mcp/references/shared-conventions.md):
background connections and Chinese annotations on UE modules you author or
change. Local atlas generation adds no UE annotations.

1. Import the atlas with `TextureTools.import_file`, then fix its settings
   with the material skill's `texture_import_fix.py` (plan, then `--apply`).
2. Build the flipbook material with
   `material_toolset_builder.py recipe fire_flipbook --execute`, or assign an
   instance through a material-instance batch.
3. Hook up the renderer and SubUV settings with `niagara-vfx-artist`, then run
   its `live_asset_verify.py`.
4. For playback changes select cases from
   [runtime acceptance](references/runtime-acceptance.md). A ready file is
   static evidence; the live material and Niagara binding is a separate check.

## References

| Need | Read |
|---|---|
| Route selection, search policy, hybrid planning, QC expectations | [workflow.md](references/workflow.md) |
| Prompts for generated smoke, dust, fire, embers and sparks | [prompt-recipes.md](references/prompt-recipes.md) |
| Continuous flipbook versus hero-plus-support versus random sprite sheet | [sequence-boundaries.md](references/sequence-boundaries.md) |
| Dimensions, grid divisibility, alpha route, material contract, frame range | [ue-niagara-readiness.md](references/ue-niagara-readiness.md) |
| Playback cases in UE | [runtime-acceptance.md](references/runtime-acceptance.md) |
