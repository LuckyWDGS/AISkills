# Scripts

`scripts/` stores the reusable Python implementation behind the Niagara VFX closed-loop tools.

- `scripts/vfx_delivery/core.py`: project-root detection, session paths, manifest IO, shared helpers
- `scripts/vfx_delivery/image_ops.py`: crop and HQ-copy helpers for cached references
- `scripts/vfx_delivery/bridge.py`: Unreal Bridge subprocess wrapper
- `scripts/vfx_delivery/*.py`: per-tool command implementations

These modules are not the primary user entry points. Use the matching files under `tools/`.
