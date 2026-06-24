# Smoke Resume Cache

## Use This When

- `material_delivery_smoke.py` 链路已经能跑，但你不想每次都重做没变的步骤。

## Purpose

`smoke_resume_cache.py` 是 `material_delivery_smoke.py --resume-cache` 的缓存面。

它会按：

- step name
- command
- 输入报告/文件指纹

决定某一步是否可以直接复用旧报告。

## Typical Commands

```powershell
python D:/Skills/skills/unreal-material-artist/tools/smoke_resume_cache.py inspect --effect WingEcho --markdown
python D:/Skills/skills/unreal-material-artist/tools/smoke_resume_cache.py prune --effect WingEcho --apply --markdown
```
