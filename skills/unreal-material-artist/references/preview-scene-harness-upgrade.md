# Preview Scene Harness Upgrade

## Use This When

- `preview_matrix.py` 里已经记录了 background / exposure / parameter tier，但还只是 intent，不是真实可执行轴。
- 你要把这些轴升级成 live preview harness 的明确接线计划。

## Purpose

`preview_scene_harness_upgrade.py` 不直接改 UE，而是输出：

- 哪些轴现在已经能执行
- 哪些轴还只是意图
- 缺什么 mapping 或缺什么 preview harness 能力
- 该怎么把 `material_variant_runner.py`、`preview_matrix.py` 和后续 live preview 串起来

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_scene_harness_upgrade.py --preview-matrix-report D:/path/to/preview-matrix.json --variant-report D:/path/to/material-variant-runner.json --background-map black=/Game/Preview/BG_Black --background-map busy=D:/Refs/busy_bg.png --exposure-map 0=0 --exposure-map high=1 --markdown
```

## Output

- `gate.ready_for_live_matrix=true`: 说明背景、曝光、参数 tier 都有可执行落点
- `recommended_commands[]`: 给后续实际跑的 `preview_matrix.py` 命令骨架

## Boundary

它是 harness-planning 工具，不是假装已经跑过 live UE。

如果 mapping 和执行面都准备好了，下一步直接用 `preview_environment_executor.py` 落真实 background / exposure / light rig 轴。
