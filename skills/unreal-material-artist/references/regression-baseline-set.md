# Regression Baseline Set

## Use This When

- 一个材质已经不再只有单 baseline。
- 你需要按 `parameter tier / carrier / background / exposure / lighting / quality` 管理多份 accepted baseline。

## Purpose

`regression_baseline_set.py` 提供：

- `capture`：先锁一份 baseline，再注册进 baseline set
- `register`：把已有 baseline JSON 纳入索引
- `resolve`：按上下文挑一份最合适的 baseline
- `list`：查看当前 effect/layer 下所有 baseline

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/regression_baseline_set.py resolve --effect WingEcho --layer RibbonTrail --parameter-tier gameplay-safe --carrier ribbon --background busy --exposure high --require-match --markdown
```
