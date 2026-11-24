# Preview planning and scoring tools

Four tools that widen a single material preview into evidence across contexts
and check that the result is readable.

| Tool | Use it when |
|---|---|
| [`preview_matrix.py`](#preview-matrix) | One preview is too narrow: the material must be judged across backgrounds, exposure, distance, angle, time, quality or parameter tiers |
| [`preview_readability_score.py`](#preview-readability-score) | A capture succeeded but the image may be nearly empty, low-contrast or off-center |
| [`preview_scene_harness_upgrade.py`](#preview-scene-harness-upgrade) | Matrix axes are still intent-only and need a concrete harness plan |
| [`preview_environment_executor.py`](#preview-environment-executor) | Background, exposure or lighting axes are staged and ready to capture |

## Preview matrix

`preview_matrix.py` builds a structured matrix around `material_preview.py
capture`. Each cell gets a unique preview effect name such as
`<matrix-effect>-cell-001`, so cells never overwrite each other. Without
`--execute` it only plans.

| Axis | Executes when |
|---|---|
| `carrier` | Always: `mesh` captures the asset thumbnail, other carriers the viewport of the carrier staged in the level (`--route` overrides) |
| `parameter_tier` | The first tier is the material itself; other tiers need `--tier-material TIER=/Game/.../MI_X` and capture as thumbnails |
| `angle`, `distance` | Viewport route with `--focus x,y,z`: the camera orbits that point at `--orbit-radius * (1 + distance)` |
| `background`, `exposure`, `lighting`, `time`, `quality` | Only their first value, meaning "whatever is staged"; the editor tools cannot switch them |

A cell that varies an axis the tools cannot drive is `pending_staging`: stage
that context, capture it with the cell's `preview_command`, and rerun with
`--cell-report CELL_ID=<report>`. Each such cell also carries a
`staging_command` for `preview_environment_executor.py`.

```powershell
python tools/preview_matrix.py --material-path /Game/Materials/M_Fire --carrier mesh --parameter-tier default,high --tier-material high=/Game/Materials/MI_Fire_High --execute --markdown
python tools/preview_matrix.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --focus 0,0,120 --angle "0,0;45,15;90,30" --execute --markdown
python tools/preview_matrix.py --package D:/reports/material-delivery-package.json --background black,busy --execute --cell-report cell-002=D:/reports/busy-capture.json
```

Use `--max-cells` to prevent an accidental huge matrix and
`--allow-large-matrix` when the size is intended.

Reports write to
`<project>/.codex/session/material-delivery/preview-matrices/<effect>/preview-matrix.json`:

- `cells[].capture`: route, material, pose, `executable`, and
  `intent_only_axes` with reasons.
- `cells[].execution.status`: `pass`, `fail` or `pending_staging`.
- `summary`: planned, executable, executed, failed and pending-staging counts.
- `gate.ready_for_regression_coverage`: true when every cell was captured
  (directly or through `--cell-report`) and none failed.
- `evidence.preview_reports[]`: the captured preview reports.

## Preview readability score

`preview_readability_score.py` reads the shaded PNGs of a preview or matrix
report and measures mean and peak luminance, visual coverage, background
contrast, center energy, edge readability, alpha coverage and near-empty
frames. It turns "the capture succeeded" into "the image is readable", which
makes it a good input for the final acceptance gate.

```powershell
python tools/preview_readability_score.py --preview-report D:/path/to/material-preview.json --require-readable --markdown
python tools/preview_readability_score.py --preview-matrix-report D:/path/to/preview-matrix.json --markdown
```

- `gate.readable=true`: the preview reaches review-ready readability.
- `findings`: names the cause, such as an empty frame, low contrast, no center
  energy or sparse alpha.

## Preview scene harness upgrade

`preview_scene_harness_upgrade.py` plans how intent-only matrix axes
(background, exposure, parameter tier) become executable. It changes nothing
in UE. It reports which axes already execute, which are still intent, which
mapping or harness capability is missing, and how to chain
`material_variant_runner.py`, `preview_matrix.py` and a live preview.

```powershell
python tools/preview_scene_harness_upgrade.py --preview-matrix-report D:/path/to/preview-matrix.json --variant-report D:/path/to/material-variant-runner.json --background-map black=/Game/Preview/BG_Black --background-map busy=D:/Refs/busy_bg.png --exposure-map
```

- `gate.ready_for_live_matrix=true`: background, exposure and parameter tier
  all have an executable target.
- `recommended_commands[]`: `preview_matrix.py` command skeletons to run next.

When mappings and execution are ready, continue with the environment
executor.

## Preview environment executor

The editor tools cannot switch background, exposure or light rigs.
`preview_environment_executor.py` resolves an environment tier into a staging
plan; after you stage the level, `--execute` captures the current frame. A
result is `pass` only with `--staged`, which confirms the environment matches
the plan. Without it the status is `captured_unstaged` and does not count as
environment evidence.

The report records the plan (`background_preset`, `exposure_bias`,
`light_rig`, and `applied_by`: `user staging` or `not staged`), the
`material_preview.py capture` command to run (optionally with `--pose`) and
the capture report. A `pass` report can be handed back to the matrix with
`preview_matrix.py --cell-report`.

```powershell
python tools/preview_environment_executor.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background busy --exposure high --markdown
python tools/preview_environment_executor.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background busy --exposure high --pose 0,-300,150,-20,90,0 --execute --staged --markdown
```
