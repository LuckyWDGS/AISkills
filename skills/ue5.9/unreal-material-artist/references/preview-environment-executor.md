# Preview Environment Executor

Epic MCP 不能切换背景、曝光或灯光组。这个工具把环境档位解析成布置计划；你在关卡里布置好之后，
`--execute` 通过 MCP 截取当前画面。只有同时传 `--staged`（确认环境已按计划布置）时结果才算 `pass`，
否则状态是 `captured_unstaged`，不会冒充环境证据。

## Use This When

- `preview_matrix.py` 的某个格子因为 `background / exposure / lighting` 轴处于 `pending_staging`。
- 你要把黑底、灰底、亮背景、杂色背景和曝光档位记录成可执行的布置计划，并留下截图证据。

## Purpose

报告里记录：

- 环境计划：`background_preset`、`exposure_bias`、`light_rig`，以及 `applied_by`（`user staging` / `not staged`）
- 要运行的 `material_preview.py capture` 命令（可带 `--pose`）
- `--execute` 时的截图报告；`pass` 的报告可以作为 `preview_matrix.py --cell-report` 交回矩阵

## Typical Commands

```powershell
python tools/preview_environment_executor.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background busy --exposure high --markdown
python tools/preview_environment_executor.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background busy --exposure high --pose 0,-300,150,-20,90,0 --execute --staged --markdown
```
