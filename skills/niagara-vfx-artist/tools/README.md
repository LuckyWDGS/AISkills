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
- `gap_diagnosis.py`
- `live_asset_verify.py`
- `unrealbridge_upstream_audit.py`
- `delivery_package.py`
- `delivery_chain_smoke.py`
- `delivery_dashboard.py`
- `delivery_finalize.py`
- `ue_smoke.py`
- `flipbook_builder.py`
- `flipbook_ue_pipeline.py`
- `effect_preview_approval.py`
- `learning_loop.py`
- `visual_layer_map.py`
- `niagara_audit.py`
- `controlled_preview.py`
- `design_compare_checklist.py`
- `effect_control_schema.py`
- `control_preset.py`
- `control_binding_generator.py`
- `control_provenance_check.py`
- `runtime_control_probe.py`
- `niagara_param_sweep.py`
- `motion_qa.py`
- `asset_cleanup.py`
- `parameter_tuning_log.py`

Each CLI bootstraps the shared implementation from `scripts/vfx_delivery/`.
Material auditing now lives in `D:/Skills/skills/unreal-material-artist/tools/material_audit.py`.
