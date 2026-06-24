# Preview Environment Executor

## Use This When

- `preview_matrix.py` 里已经有 `background / exposure` 轴，但你不想它们只停在 intent。
- 你要把黑底、灰底、亮背景、杂色背景和曝光档位变成真实执行的 preview harness。

## Purpose

`preview_environment_executor.py` 会把环境轴翻译成一次真正的 `material_preview.py render` 执行，并传入：

- `background_preset`
- `exposure_bias`
- `light_rig`

执行后会保留：

- 环境执行报告
- 内层 `material_preview.py` 报告路径
- 后续 readability / regression 可直接消费的 preview evidence

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_environment_executor.py --material-path /Game/Materials/MI_WingEcho --carrier ribbon --background busy --exposure high --execute --project UnrealAI --endpoint 127.0.0.1:57404 --markdown
```
