# Preview Environment Executor

> **仅规划：** 原先 `--execute` 依赖的 UnrealBridge 渲染 harness 已移除。Epic MCP 没有背景、曝光或灯光档位，`--execute` 会被拒绝；按计划在关卡里布置好环境后，用 `material_preview.py capture` 截图，再把报告交给 readability / regression。

## Use This When

- `preview_matrix.py` 里已经有 `background / exposure` 轴，但你不想它们只停在 intent。
- 你要把黑底、灰底、亮背景、杂色背景和曝光档位记录成可执行的布置计划。

## Purpose

`preview_environment_executor.py` 会把环境轴解析成计划，并生成对应的 `material_preview.py capture` 命令。计划里记录：

- `background_preset`
- `exposure_bias`
- `light_rig`

报告里保留：

- 环境计划（背景预设、曝光偏移、灯光组）
- 布置好环境后要运行的 capture 命令
- capture 产出的 `material_preview` 报告可直接给 readability / regression 使用

## Typical Command

```powershell
python tools/preview_environment_executor.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background busy --exposure high --project <Project> --markdown
```
