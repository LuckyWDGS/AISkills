# Tools

`tools/` contains the user-facing CLI entry points for the Niagara VFX closed-loop workflow.

- `reference_cache.py`
- `reference_acceptance.py`
- `layer_evidence.py`
- `preview_approval.py`
- `asset_plan.py`
- `integration_plan.py`
- `niagara_asset_assistant.py`
- `ue_write_helpers.py`
- `visual_diff_qa.py`
- `delivery_package.py`
- `learning_loop.py`
- `visual_layer_map.py`
- `niagara_audit.py`
- `controlled_preview.py`
- `design_compare_checklist.py`
- `asset_cleanup.py`
- `parameter_tuning_log.py`

Each CLI bootstraps the shared implementation from `scripts/vfx_delivery/`.
Material auditing now lives in `D:/Skills/skills/unreal-material-artist/tools/material_audit.py`.
