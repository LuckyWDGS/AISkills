# Library Promotion Gate

## Use This When

- 某个材质已经做完，但你要判断它能不能进入 reusable library 作为 approved stock。
- 你不想只靠“看起来不错”就把候选资产升成库资产。

## Purpose

`library_promotion_gate.py` 会把：

- acceptance gate
- parameter schema
- source provenance
- preview matrix
- preview readability

这些证据合起来判断是否够资格进入 reusable library。

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/library_promotion_gate.py --asset-id abc123 --report-path D:/path/to/delivery-v2.json --report-path D:/path/to/material-parameter-schema.json --report-path D:/path/to/material-source-provenance.json --report-path D:/path/to/preview-matrix.json --report-path D:/path/to/preview-readability-score.json --require-ready --markdown
```

## Optional Apply

如果已经有 library record，并且证据全通过，可以：

```powershell
python D:/Skills/skills/unreal-material-artist/tools/library_promotion_gate.py --asset-id abc123 --report-path ... --apply --require-ready
```

它只会把现有 catalog record 升到 `approved`，不会替你自动注册一个不存在的候选资产。

## Boundary

这是“库晋升 gate”，不是材质 graph 生产工具，也不是 Niagara 系统级 ready gate。
