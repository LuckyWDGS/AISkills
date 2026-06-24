# Material Regression

## Use This When

- A `material_preview.py` result has been visually accepted and should become the baseline.
- You are about to optimize, change textures, tune parameters, rebuild a material, or refactor graph nodes.
- A `delivery_packager.py` report contains preview evidence that should be locked for future comparisons.

## Purpose

`material_regression.py` protects accepted material previews from accidental visual drift. It locks a baseline preview, copies the preview images into the regression folder, and compares later `material_preview.py` reports against that baseline.

It reports:

- mean RGB difference
- changed pixel ratio
- brightness delta
- alpha coverage delta
- visual/luminance coverage delta
- centroid shift in pixels
- complexity preview delta when both previews contain complexity images
- generated heat and composite diff images

## Table Of Contents

- [Lock A Baseline](#lock-a-baseline)
- [Compare A New Preview](#compare-a-new-preview)
- [Explain A Failed Comparison](#explain-a-failed-comparison)
- [Thresholds](#thresholds)
- [Gate Meaning](#gate-meaning)
- [Recommended Flow](#recommended-flow)

## Lock A Baseline

From a preview report:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py baseline --effect WingEcho --layer RibbonTrail --preview-report D:/path/to/material-preview.json --label accepted-v001 --markdown
```

From a delivery package that already contains preview evidence:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py baseline --package D:/path/to/material-delivery-package.json --label accepted-v001 --markdown
```

The baseline is written to:

```text
<project>/.codex/session/material-delivery/regression/<effect-layer>/material-regression-baseline.json
```

Baseline images are copied under:

```text
<project>/.codex/session/material-delivery/regression/<effect-layer>/baseline-images/
```

## Compare A New Preview

Using the default baseline for an effect/layer:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py compare --effect WingEcho --layer RibbonTrail --preview-report D:/path/to/new-material-preview.json --strict --markdown
```

Using an explicit baseline:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py compare --baseline D:/path/to/material-regression-baseline.json --preview-report D:/path/to/new-material-preview.json --strict --markdown
```

The comparison writes JSON/Markdown plus diff images under:

```text
<project>/.codex/session/material-delivery/regression/<effect-layer>/comparisons/<label>/
```

## Explain A Failed Comparison

When a comparison fails, pair the regression report with before/after audit reports:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_diff_refactor.py diff --before-audit D:/reports/before/material-audit.json --after-audit D:/reports/after/material-audit.json --before-domain-audit D:/reports/before/material-domain-audit.json --after-domain-audit D:/reports/after/material-domain-audit.json --regression-report D:/reports/material-regression-comparison.json --effect WingEcho --layer RibbonTrail --label optimize-pass-01 --markdown
```

This produces a likely-cause list for route, output-chain, parameter, graph, finding, and budget changes. Rerun `material_audit.py` with `--include-raw-graph` on both revisions when exact node and connection provenance matters.

## Thresholds

Defaults are intentionally conservative:

- `--max-mean-diff 3.0`
- `--max-changed-ratio 0.025`
- `--max-alpha-coverage-delta 0.03`
- `--max-visual-coverage-delta 0.04`
- `--max-brightness-delta 5.0`
- `--max-centroid-shift 12.0`
- `--max-complexity-mean-diff 8.0`

Use tighter thresholds for locked final art. Use looser thresholds for noisy smoke, fire, or stochastic previews, but record why in the delivery notes.

## Gate Meaning

`gate.passed=true` means the new preview did not exceed configured drift thresholds. It does not mean the material is artistically approved. It only means the preview stayed close enough to the locked baseline for the measured dimensions.

If a baseline has a complexity image and the current preview lacks one, the comparison records an error. That catches accidental loss of complexity evidence during optimization passes.

## Recommended Flow

1. Render `material_preview.py` on the intended carrier.
2. Visually accept the preview against the reference.
3. Build or refresh `delivery_packager.py` with that preview report.
4. Lock a regression baseline from the package.
5. After any material edit, render a new preview.
6. Run `material_regression.py compare --strict`.
7. If the comparison fails, inspect the composite and heat images.
8. Run `graph_diff_refactor.py diff` against before/after audits to identify likely material-side causes.
9. Fix, revert, or intentionally accept a new baseline only after the visual and structural evidence agree.
