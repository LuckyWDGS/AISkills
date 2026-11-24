# Preview Matrix

## Use This When

- One preview is not enough to judge a material across practical contexts.
- A VFX material reads well on black but may disappear on bright or busy backgrounds.
- Regression evidence should include distance, angle, time, quality, and parameter-tier coverage.

## Purpose

`preview_matrix.py` builds a structured preview matrix around `material_preview.py capture`.
Each cell gets a unique preview effect name like `<matrix-effect>-cell-001`, so cell evidence
does not overwrite its neighbours. Without `--execute` it only plans.

## What Epic MCP Can Drive

| Axis | Executes when |
| --- | --- |
| `carrier` | always: `mesh` captures the asset thumbnail, other carriers the viewport of the carrier staged in the level (`--route` overrides) |
| `parameter_tier` | the first tier is the material itself; other tiers need `--tier-material TIER=/Game/.../MI_X` and capture as thumbnails (a viewport shows the staged actor's material) |
| `angle`, `distance` | viewport route with `--focus x,y,z`: the camera orbits that point at `--orbit-radius * (1 + distance)` looking at it |
| `background`, `exposure`, `lighting`, `time`, `quality` | only their first value, meaning "whatever is staged"; MCP has no control for them |

A cell that varies an axis MCP cannot drive is `pending_staging`: stage that context, capture
it with the cell's `preview_command`, and rerun with `--cell-report CELL_ID=<report>`.
Each such cell also carries a `staging_command` for `preview_environment_executor.py`.

## Typical Commands

```powershell
python tools/preview_matrix.py --material-path /Game/Materials/M_Fire --carrier mesh --parameter-tier default,high --tier-material high=/Game/Materials/MI_Fire_High --execute --markdown
python tools/preview_matrix.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --focus 0,0,120 --angle "0,0;45,15;90,30" --execute --markdown
python tools/preview_matrix.py --package D:/reports/material-delivery-package.json --background black,busy --execute --cell-report cell-002=D:/reports/busy-capture.json
```

Use `--max-cells` to prevent accidental huge matrices and `--allow-large-matrix` when the size is intentional.

## Output

Reports write under:

```text
<project>/.codex/session/material-delivery/preview-matrices/<effect>/preview-matrix.json
```

- `cells[].capture`: route, material, pose, `executable`, and `intent_only_axes` with reasons.
- `cells[].execution.status`: `pass`, `fail` or `pending_staging`.
- `summary`: planned, MCP-executable, executed, failed and pending-staging counts.
- `gate.ready_for_regression_coverage`: true only when every cell was captured (directly or via `--cell-report`) and none failed.
- `evidence.preview_reports[]`: the captured `material_preview` reports.
