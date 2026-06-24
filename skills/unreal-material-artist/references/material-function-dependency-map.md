# Material Function Dependency Map

## Use This When

- 项目里 Material Function 开始变多，复用热点和隐形风险看不清。
- 你需要知道哪些函数被很多材质依赖，哪些函数过大、过重、缺文档、可能需要治理。

## Purpose

`material_function_dependency_map.py` 会综合：

- `material_function_linter.py`
- `material_audit.py` 里的 function-call 线索

输出：

- function -> material 的依赖关系
- reuse hotspot
- large/switch-heavy function 风险
- duplicate function name 风险

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_function_dependency_map.py --function-linter-report D:/path/to/material-function-linter.json --audit-report D:/path/to/material-audit.json --markdown
```

## Output

- `functions[]`
- `materials[]`
- `hotspots[]`

它更偏项目治理和后续 graph refactor 的风险地图。
