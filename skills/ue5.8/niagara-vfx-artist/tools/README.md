# Tools

`tools/` contains the user-facing CLI entry points for the Niagara VFX closed-loop workflow.

- `reference_cache.py`
- `reference_acceptance.py`
- `layer_evidence.py`
- `preview_approval.py`
- `asset_plan.py`
- `integration_plan.py`
- `niagara_asset_assistant.py`
- `visual_diff_qa.py`
- `gap_diagnosis.py`
- `live_asset_verify.py`
- `delivery_package.py`
- `delivery_chain_smoke.py`
- `delivery_dashboard.py`
- `delivery_finalize.py`
- `ue_smoke.py`
- `flipbook_builder.py`
- `effect_preview_approval.py`
- `learning_loop.py`
- `visual_layer_map.py`
- `niagara_audit.py`
- `design_compare_checklist.py`
- `effect_control_schema.py`
- `control_preset.py`
- `control_binding_generator.py`
- `control_provenance_check.py`
- `motion_qa.py`
- `asset_cleanup.py`
- `parameter_tuning_log.py`

Every CLI has the same three-line body: `_launch.py` puts `scripts/` on `sys.path` and runs `main()` of the `scripts/vfx_delivery/` module with the same name (`ALIASES` lists the two that differ). Add a tool by copying any shim; `unreal-engine-mcp/scripts/test_tool_entry_points.py` checks that every shim resolves.
Material auditing now lives in `../unreal-material-artist/tools/material_audit.py`.
