# Preview Matrix

> **Plan only:** the UnrealBridge executor behind `--execute` was removed. Epic MCP has no camera, lighting, background or exposure axes, so each cell's command is a `material_preview.py capture`; stage that context in the level, capture it, and pass the reports on with `--preview-report`.

## Use This When

- One preview is not enough to judge a material across practical contexts.
- A VFX material reads well on black but may disappear on bright or busy backgrounds.
- Regression evidence should include distance, angle, time, quality, and parameter-tier coverage.

## Purpose

`preview_matrix.py` builds a structured preview matrix around `material_preview.py`.

It writes a plan with one capture command per cell. Each cell uses a unique preview effect name like `<matrix-effect>-cell-001`, so preview JSON/PNG evidence does not overwrite neighboring cells. `--execute` is refused.

## Typical Commands

Plan a small matrix:

```powershell
python tools/preview_matrix.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background black,busy --angle "0,0;45,10" --quality low,medium --markdown
```

Plan from a delivery package:

```powershell
python tools/preview_matrix.py --package D:/reports/material-delivery-package.json --background black,neutral,busy --distance 0,2,5 --time 0.25,1.0 --quality low,high --markdown
```

## Axes

- `background`: review context only for now.
- `exposure`: review context only for now.
- `distance`: passed to `material_preview.py`.
- `angle`: `yaw,pitch`, passed to `material_preview.py`.
- `time`: passed as `--sim-time`.
- `parameter_tier`: review context only for now; use prepared MIs or `material_instance_batch.py` for real value changes.
- `quality`: maps to resolution unless `--resolution` is supplied.
- `carrier` and `lighting`: passed to `material_preview.py`.

Use `--max-cells` to prevent accidental huge matrices. Use `--allow-large-matrix` when the matrix size is intentional.

## Output

Reports write under:

```text
<project>/.codex/session/material-delivery/preview-matrices/<effect>/preview-matrix.json
```

Important fields:

- `cells[]`: planned context and command per preview.
- `summary`: planned/executed/pass/fail counts.
- `gate.ready_for_regression_coverage`: stays false; coverage comes from the captured cell reports.
- `evidence.preview_reports[]`: executed `material_preview.py` report paths.

## Limitation

Background, exposure, and parameter-tier values are currently tracked as matrix intent rather than fully executed scene or parameter mutations. Use this as a structured coverage plan first, then promote missing axes into `material_preview.py` or prepared MI variants when needed.
