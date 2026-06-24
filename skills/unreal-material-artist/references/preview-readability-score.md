# Preview Readability Score

## Use This When

- `material_preview.py` 截图成功了，但你怀疑画面“其实几乎看不见”。
- 你想量化预览是否真的可读，而不是只知道 `shaded_ok=true`。
- VFX 材质在黑底能看，在实战背景里容易消失，需要一个更硬的可读性门。

## What It Scores

`preview_readability_score.py` 会从 `material_preview.py` 或 `preview_matrix.py` 的 shaded PNG 里提取：

- 亮度均值/峰值
- 视觉覆盖率
- 背景对比
- 中心区域能量
- 边缘可读性
- alpha 覆盖
- 几乎空画面的检测

## Typical Commands

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_readability_score.py --preview-report D:/path/to/material-preview.json --require-readable --markdown
```

```powershell
python D:/Skills/skills/unreal-material-artist/tools/preview_readability_score.py --preview-matrix-report D:/path/to/preview-matrix.json --markdown
```

## Output

- `gate.readable=true`: 当前预览至少达到了 review-ready 的可读性
- `findings`: 会明确指出是空画面、对比不够、中心没能量，还是 alpha 太稀

## Why It Matters

它解决的是“截图成功但画面无效”的问题，适合放进最终 acceptance gate。
