---
name: vfx-flipbook-generator
description: Plan, generate, extend, repair, and pack VFX flipbook atlases for smoke, dust, powder, fire, flame, embers, sparks, explosions, mist, clouds, and other sprite/SubUV effects. Use when Codex needs to turn short alpha videos, sparse footage, still references, web-searched motion examples, or text direction into a production-ready flipbook grid or atlas; when the requested grid has more cells than the usable source samples; when the user asks for a flipbook, sequence atlas, SubUV atlas, sprite sheet, missing-frame extension, or wants system-imagegen-generated smoke, fire, or particle frames assembled into a power-of-two atlas.
---

# VFX Flipbook Generator

Use this skill when the user wants a flipbook atlas, not just a single concept image.

This skill owns three things:

1. Decide whether the job should use source footage, hybrid generation, or full generation.
2. Use search/reference gathering and image generation when source material is too short or too weak.
3. Assemble frames into a power-of-two atlas that is ready for SubUV-style use, preferring 2K or 4K source delivery when the platform budget allows.
4. Scaffold a reusable flipbook job pack from a short request such as `smoke 12x12 6s`.
5. Turn a scaffolded job into a per-frame batch plan before the actual image generation run.
6. Run the batch plan one phase at a time, stop on anchor approval gates, and prefer image-reference edit for intra-phase fill after an anchor is accepted.
7. Gate Unreal/Niagara delivery with a UE readiness check before calling an atlas direct material/SubUV-ready.

## Workflow

1. Quantify the source before committing to a grid.
   - If the user only gives a short natural-language request like `smoke 12x12 6s`, scaffold a job pack first.
   - Run:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_job_scaffold.py "smoke 12x12 6s"
```

   - The scaffold writes:
     - route advice
     - search queries
     - anchor prompts
     - output folder plan
     - packing command template
   - If the user gives a video, get the usable clip duration, fps, and approximate source sample count.
   - Run:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_route_advisor.py --grid 12x12 --effect dust --clip-duration 6.2 --source-fps 23.976 --markdown
```

   - Treat the route result as the first decision, not as a hard law.

2. Use the correct route.
   - `direct-extract`
     - Use when source sample pressure is healthy enough for the requested grid.
     - Prefer `D:/Skills/skills/vfx-flipbook-generator/tools/flipbook_builder.py`.
     - The tool auto-discovers local FFmpeg binaries under `D:/Skills/skills/vfx-flipbook-generator/tools/ffmpeg` before falling back to system `PATH`.
     - Keep `--fit contain` unless you explicitly want cropping. `contain` scales the full source frame into the cell and pads as needed; `cover` crops to fill.
   - `hybrid`
     - Use when the source has some good motion but not enough clean temporal coverage.
     - Keep the best real motion from source footage.
     - Generate missing states or bridge frames with system `imagegen` by default.
     - Pack the final frame set with `frame_atlas_packer.py`.
   - `full-generated`
     - Use when the user has little or no usable source footage, or when the desired effect is fundamentally custom and source reuse would fight the art direction.
     - Gather references first, then generate a consistent frame family with system `imagegen` by default, then pack it.

3. Search when reference coverage is weak or the user explicitly asks for it.
   - If the user explicitly asks to search, browse.
   - Use web/image search to understand motion language, shape breakup, density, timing, and silhouette.
   - Search for reference, not for direct asset ripping.
   - Do not scrape a stock atlas and pass it off as newly made work.
   - Record the useful search queries and what each reference contributed.
   - Good search targets are motion cues such as `falling dust alpha`, `smoke plume reference`, `torch flame side view`, `embers burst reference`, not just generic beauty images.

4. When generating frames, keep invariants locked.
   - Use one fixed canvas size for the whole family.
   - Prefer native `2048x2048` or `4096x4096` power-of-two generation/packing for final atlas sources. Use `1024x1024` only for chat previews, quick reviews, mobile-only assets, or an explicit low-budget derivative.
   - When the provider cannot natively generate 2K/4K, keep the best raw output, document the limitation, and create a 2K/4K derivative for delivery only if the user accepts that it is an upscale rather than recovered detail.
   - Keep one fixed camera angle.
   - Keep one fixed background policy:
     - black when extracting luminance-style VFX cards
     - transparent when the route reliably supports it
   - Keep the subject centered and similarly scaled from frame to frame.
   - Keep the same effect family and shell structure.
   - Do not let the model change the effect into a different phenomenon halfway through the sequence.
   - Prefer generating 4-8 anchor states first, review them, then fill the family, instead of asking for 100+ uncontrolled frames in one leap.
   - After a phase anchor is accepted, prefer image-reference edit for the rest of that phase before falling back to fresh text generation.
   - Before asking for strict continuity, check [references/sequence-boundaries.md](references/sequence-boundaries.md) and decide whether the effect truly needs ordered time evolution or whether a randomizable sprite set would be better.

5. Do not hide frame scarcity with slow playback alone.
   - If the route advisor says the source is thin, do not assume Niagara time stretching will save it.
   - For smoke, dust, powder, and mist:
     - keep internal motion reasonably close to source timing
     - let Niagara extend life with size, alpha, drag, and lingering support layers
   - For flame and hero fire:
     - treat low source coverage as a generation problem earlier
     - slow playback exposes stepping quickly

6. Pack frames into an atlas.
   - For source-video extraction, use `flipbook_builder.py`.
   - Prefer `--fit contain` for video-derived flipbooks when the user wants the full frame preserved.
   - For pre-made frame folders, generated anchor families, or hand-curated PNG frames, use:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/frame_atlas_packer.py D:/path/to/frames --grid 12x12 --cell-size 256x256 --out-dir D:/path/to/out --atlas-name smoke_flipbook.png
```

   - Default to power-of-two final atlas output.
   - For final Unreal/Niagara delivery, prefer `2048x2048` or `4096x4096` atlases with exact grid divisibility. Downscale from that source when smaller variants are needed.
   - Prefer padding to power-of-two when the raw atlas does not land on exact power-of-two dimensions. This keeps the packed cells unscaled and records the raw pre-snap size in the manifest.
   - For direct UE/Niagara SubUV output, require the final atlas dimensions to divide evenly by columns and rows. A `10x10` review sheet at `1024x1024` is not direct production SubUV-ready under the default contract.

7. Run a quick QC pass before delivery.
   - Check that there are no obvious blank accidental rows or columns.
   - Check that alpha/background policy stayed consistent.
   - Check that frame-to-frame scale drift is not extreme.
   - Check whether transparent padding is expected or a sign the fit mode should change from `contain` to `cover`.
   - If the atlas is for Unreal, report:
     - grid columns and rows
     - frame count
     - final atlas dimensions
     - exact cell dimensions or a grid-divisibility warning
     - raw pre-snap dimensions when snapped
     - suggested playback fps
     - frame order, start frame, end frame, alpha policy, and blend-mode recommendation
   - For Unreal-bound atlases, run:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/ue_flipbook_readiness.py D:/path/to/atlas.png --manifest D:/path/to/flipbook-manifest.json --mode both --alpha-policy auto
```

   - When a folder contains multiple generated candidates, build a selection catalog so the user can see recommended, usable, conditional, and blocked variants in one place:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_asset_catalog.py D:/path/to/atlas-folder --out D:/path/to/atlas-folder/atlas-catalog.md --json-out D:/path/to/atlas-folder/atlas-catalog.json
```

8. Hand off to the right downstream skill when needed.
   - Use `niagara-vfx-artist` when the atlas needs UE/Niagara hookup, SubUV setup, or renderer validation.
   - Use `unreal-material-artist` when the material route, blend mode, alpha behavior, or flipbook texture strategy needs material-side ownership.
   - Use system built-in `imagegen` as the default image generation route for generated frames and reference-image generation.
   - Use `cm-imagegen` only when the user explicitly wants the local CLI route or when a local automation path is more important than the default manual system-imagegen flow.

## Commands

Source-video route:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/tools/flipbook_builder.py build D:/clip.mov --start 0.2 --end 6.5 --grid 12x12 --frames 144 --cell-size 171x341 --fit contain --background transparent --atlas-size-mode pad-to-power-of-two
```

Route decision:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_route_advisor.py --grid 12x12 --effect smoke --clip-duration 3.5 --source-fps 25 --markdown
```

Job scaffold from a short request:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_job_scaffold.py "smoke 12x12 6s" --out-root D:/flipbook-jobs
```

Frame-plan scaffold with default system-imagegen workflow:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_plan.py D:/flipbook-jobs/smoke-12x12-6s/.../job-spec.json --prompt-suffix "gravity-driven downward motion, no environment"
```

Phase runner with anchor approval gates:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_runner.py status D:/flipbook-jobs/smoke-12x12-6s/.../frame-plan.json
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_runner.py run D:/flipbook-jobs/smoke-12x12-6s/.../frame-plan.json
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_runner.py import-frame D:/flipbook-jobs/smoke-12x12-6s/.../frame-plan.json --frame 1 --path "D:/path/to/generated/frame_001.png" --approve-anchor
```

Generated-frame packing:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/frame_atlas_packer.py D:/frames/smoke_a --grid 10x10 --cell-size 256x256 --fit contain --background transparent --atlas-size-mode pad-to-power-of-two --out-dir D:/atlas_out --atlas-name smoke_10x10.png
```

Unreal/Niagara readiness gate:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/ue_flipbook_readiness.py D:/atlas_out/smoke_10x10.png --manifest D:/atlas_out/flipbook-manifest.json --mode both --alpha-policy auto
```

Asset catalog for a candidate folder:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_asset_catalog.py D:/atlas_out --out D:/atlas_out/atlas-catalog.md --json-out D:/atlas_out/atlas-catalog.json
```

Resize a ready atlas/alpha pair to 2K and 4K delivery derivatives:

```powershell
python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_atlas_resizer.py D:/atlas_out/fx_sheet_4x4_1024.png --alpha-path D:/atlas_out/fx_sheet_alpha_4x4_1024.png --grid 4x4 --targets 2048 4096 --out-dir D:/atlas_out/highres
```

## Reference Map

- [references/workflow.md](references/workflow.md)
  Use for route selection, search policy, hybrid planning, and QC expectations.

- [references/prompt-recipes.md](references/prompt-recipes.md)
  Use when the user needs generated smoke, dust, powder, fire, embers, sparks, or other VFX frame families through system `imagegen` or another image route.

- [references/sequence-boundaries.md](references/sequence-boundaries.md)
  Use when deciding whether a requested effect should be a true continuous flipbook, a mixed hero-plus-support setup, or a non-continuous random sprite sheet.

- [references/ue-niagara-readiness.md](references/ue-niagara-readiness.md)
  Use before calling an atlas direct Unreal material-ready or Niagara SubUV-ready. Covers dimensions, grid divisibility, alpha/luma route, material contract, Niagara frame range, and common non-smoke/fire/dust flipbook uses.

- [scripts/flipbook_route_advisor.py](scripts/flipbook_route_advisor.py)
  Use to estimate duplicate-frame pressure and select `direct-extract`, `hybrid`, or `full-generated`.

- [scripts/frame_atlas_packer.py](scripts/frame_atlas_packer.py)
  Use to turn a folder of PNG frames into a power-of-two flipbook atlas plus manifest.

- [scripts/ue_flipbook_readiness.py](scripts/ue_flipbook_readiness.py)
  Use to statically check whether an atlas and manifest are ready, conditional, or blocked for direct UE material/Niagara SubUV use.

- [scripts/flipbook_asset_catalog.py](scripts/flipbook_asset_catalog.py)
  Use to scan a folder of atlas PNGs, manifests, and readiness reports into a Markdown/JSON selection catalog with RGB/alpha pairing, status summaries, warnings, and UE/Niagara handoff notes.

- [scripts/flipbook_atlas_resizer.py](scripts/flipbook_atlas_resizer.py)
  Use to make 2K/4K power-of-two derivatives from a ready atlas and optional alpha support PNG, preserving grid divisibility and writing a new manifest. Prefer native 2K/4K generation when available; use resizing as a delivery derivative when the provider only gave a smaller source.

- [scripts/flipbook_job_scaffold.py](scripts/flipbook_job_scaffold.py)
  Use to turn a short request into a full working package with route advice, search queries, prompts, folders, and packing templates.

- [scripts/flipbook_batch_plan.py](scripts/flipbook_batch_plan.py)
  Use to turn a scaffolded job into a per-frame prompt plan plus a default system-imagegen workflow and an optional `cm-imagegen` fallback script.

- [scripts/flipbook_batch_runner.py](scripts/flipbook_batch_runner.py)
  Use to coordinate a frame plan one phase at a time, stop for anchor approval, and prefer image-reference edit for phase fill after an anchor is accepted. Its default provider mode is system `imagegen`.

- [tools/flipbook_builder.py](tools/flipbook_builder.py)
  Use to inspect a source video, extract frames with local FFmpeg, and build a PNG atlas plus manifest from inside this skill.
