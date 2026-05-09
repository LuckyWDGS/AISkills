# Capability Gap Map

This map describes what is still missing to turn a reference image or text brief into a fully usable Niagara effect with minimal guesswork.

## Already Covered

- Reference caching, cropping, HQ copies, and active/rejected/debug separation
- Visual layer mapping
- Material audit
- Niagara audit
- Controlled preview
- Design comparison checklist
- Asset cleanup
- Parameter tuning log
- End-to-end workflow docs

## First-Pass Coverage Added

### 1. Reference Acceptance Gate

Needed:
- approval status for each anchor
- clarity threshold
- “use this one only” lock for the chosen design image
- rejection/quarantine of drifted or low-signal references

Current first-pass tool:
- `tools/reference_acceptance.py`

Why it matters:
- without a strict anchor gate, later texture and preview generation can drift from the real target

### 2. Layer Evidence Extraction

Needed:
- automatic crop/hotspot suggestions
- per-layer evidence capture
- region to layer-name mapping
- visible proof for silhouette, residue, spacing, and motion cues

Why it matters:
- layer names alone are not enough; each layer needs visible proof from the plate

Current first-pass tool:
- `tools/layer_evidence.py`

### 3. Preview Approval Gate

Needed:
- side-by-side reference vs preview review
- pass / fail / revise status
- structured difference notes
- preset library for repeated camera/background setups

Why it matters:
- a pretty preview is not the same as an approved implementation target

Current first-pass tool:
- `tools/preview_approval.py`

### 4. Asset Plan Generator

Needed:
- minimum texture/material/Niagara asset list
- LOD and low-end variant plan
- naming and folder convention output
- platform budget check before implementation

Why it matters:
- the implementation should start from a budgeted asset plan, not from ad hoc authoring

Current first-pass tool:
- `tools/asset_plan.py`

### 5. Integration Hookup Planner

Needed:
- socket / bone / notify / Blueprint / GAS / Sequencer choice
- user parameter list
- trigger timing and source transform ownership
- runtime attachment contract

Why it matters:
- a correct standalone effect can still fail if it cannot be driven by the game

Current first-pass tool:
- `tools/integration_plan.py`

### 6. Write-Side UE Helpers

Needed:
- create / duplicate / reset material assets
- create / duplicate Niagara systems and emitters
- apply effect type, scalability, and folder/tag rules
- cleanup stale or superseded assets at the source

Why it matters:
- audits alone do not complete the loop; we also need safe creation and repair tools

Current first-pass tool:
- `tools/ue_write_helpers.py`

### 7. Visual Diff QA

Needed:
- actual captured image comparison, not only checklist notes
- silhouette, density, width, spacing, brightness, and motion-path diffs
- archived iteration comparisons

Why it matters:
- the eye still needs structure, not just a checklist

Current first-pass tool:
- `tools/visual_diff_qa.py`

### 8. Delivery Packaging

Needed:
- final asset manifest
- approved previews
- tuning recipe
- low-end fallback note
- risk and limitation note

Why it matters:
- the next person should be able to find the active assets and reuse them without guessing

Current first-pass tool:
- `tools/delivery_package.py`

### 9. Learning Loop

Needed:
- auto-generated case study from each successful effect
- reusable parameter recipe extraction
- success/failure pattern library
- separation of approved anchors and rejected variants

Why it matters:
- the system should get better after every shipped effect

Current first-pass tool:
- `tools/learning_loop.py`

## Still Needs Tightening

- Reference acceptance should eventually reject drift automatically based on visual evidence, not only manual review.
- Layer evidence should eventually understand motion arcs and multi-frame cues, not only still-image hotspots.
- Preview approval should eventually integrate side-by-side visual diff automatically at review time.
- Asset planning should eventually understand project-specific naming conventions and existing reusable masters.
- Integration planning should eventually read real skeleton/socket/notify context from the target project.
- Write-side UE helpers should eventually cover richer Niagara authoring and safe retirement of stale assets.
- Visual diff QA should eventually compare motion clips, not only still frames.
- Delivery packaging should eventually pull final active assets directly from the project instead of relying on manual final lists.
- Learning loop should eventually auto-build stronger case studies from shipped effects without manual curation.

## Priority Order

1. Reference acceptance gate
2. Layer evidence extraction
3. Preview approval gate
4. Write-side UE helpers
5. Asset plan generator
6. Integration hookup planner
7. Visual diff QA
8. Delivery packaging
9. Learning loop

## End Goal

The skill is complete only when a user can provide a reference or brief, approve a grounded UE-achievable preview, and then reach a shippable effect with minimal drift, clear cleanup, and a reusable delivery record.
