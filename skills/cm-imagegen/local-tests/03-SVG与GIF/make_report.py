import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
results = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
assert len(results) == 4, "Wait until all four requests have finished."
audits = []
for case in results:
    for original in case["original_files"]:
        path = Path(original["path"])
        data = path.read_bytes()
        with Image.open(path) as im:
            im.load()
            audits.append({"case": case["id"], "path": str(path),
                           "requested_format": case["format"], "actual_format": im.format,
                           "dimensions": list(im.size), "frames": getattr(im, "n_frames", 1),
                           "signature_hex": data[:16].hex(), "sha256": hashlib.sha256(data).hexdigest()})
(ROOT / "media-audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding="utf-8")
assert len(audits) == 2 and all(a["actual_format"] == "PNG" for a in audits)
assert all("GIF output is not enabled for this request." in c["result"].get("error", "") for c in results if c["format"] == "gif")

font_path = "C:/Windows/Fonts/msyh.ttc"
font = ImageFont.truetype(font_path, 25)
small = ImageFont.truetype(font_path, 20)
canvas = Image.new("RGB", (1380, 770), "#f5f2eb")
draw = ImageDraw.Draw(canvas)
draw.text((30, 18), "SVG 请求实测：两张实际返回文件均为 PNG", font=font, fill="#162d32")
for i, audit in enumerate(audits):
    x = 30 + i * 675
    with Image.open(audit["path"]) as im:
        tile = im.convert("RGBA")
        tile.thumbnail((645, 645), Image.Resampling.LANCZOS)
        canvas.paste(tile, (x, 65), tile)
    title = "机械温室" if i == 0 else "运河小镇"
    draw.text((x, 724), title + " · PNG · 1254 × 1254", font=small, fill="#162d32")
canvas.save(ROOT / "实际返回PNG预览.jpg", quality=92)

rows = []
for case in results:
    actual = "PNG，1254×1254" if case["format"] == "svg" else "无文件；HTTP 400"
    verdict = "格式不符，未生成 SVG" if case["format"] == "svg" else "GIF 输出未启用"
    rows.append(f"| {case['label']} | {case['format'].upper()} | {actual} | {verdict} | {case['elapsed_seconds']:.2f} 秒 |")
report = """# SVG / GIF 四次实测记录

本轮完成 SVG 两次独立请求、GIF 两次独立请求。原生 SVG 成功数 **0/2**，原生 GIF 成功数 **0/2**。实际保存两张 PNG 原图。

## 条件

- 日期：2026-11-07（本地测试目录日期）。
- 模型：`gpt-image-2.6-sunburst`。
- 路径：配置的 cm 提供商，`https://209.87.95.5:18081/v1/images/generations`。
- 共同显式参数：`quality=max`、`complexity=high`、`n=1`。
- SVG：`output_format=svg`、`size=1024x1024`；提示词明确要求可编辑路径、无位图嵌入。
- GIF：`output_format=gif`、`size=auto`、`frame_count=9`、`frame_duration_ms=200`；目标为 1.8 秒循环。
- 每个案例只提交一次，未自动重试，也未更换提供商或接口。

## 结果

| 案例 | 请求格式 | 实际返回 | 判定 | 耗时 |
| --- | --- | --- | --- | --- |
""" + "\n".join(rows) + """

## 检查结论

两张 SVG 请求的返回文件均具有 PNG 文件头，Pillow 可完整解码，均为单帧 1254×1254。图像有矢量插画风格，但文件中没有 SVG XML 和可编辑矢量路径。尺寸也未满足请求的 1024×1024，只有方形比例符合。

两次 GIF 请求均返回相同的服务端错误：`GIF output is not enabled for this request.`，未返回任何动画文件，因此无法评估帧数、运动或循环质量。

这些结果只证明本轮账号与网关路径没有成功提供原生 SVG/GIF。尚不能由此判定限制来自账号权限、网关适配还是上游模型能力；没有检查或更改服务端配置。

## 产物与证据

- [机械温室 PNG 原图](svg_01_greenhouse/svg_01_greenhouse.png)
- [运河小镇 PNG 原图](svg_02_canal/svg_02_canal.png)
- [两张 PNG 预览](实际返回PNG预览.jpg)
- [四次请求汇总](results.json)
- [文件格式、尺寸与 SHA256 独立检查](media-audit.json)
- 各案例目录中的 `request.json`、`stdout.json`、`stderr.txt` 保存了本轮请求与响应记录。

原始返回文件保持不变；预览仅用于展示。没有将 PNG 改名、转换或包装成 SVG/GIF 来替代实测结果。
"""
(ROOT / "测试报告.md").write_text(report, encoding="utf-8")
print(json.dumps({"completed_requests": len(results), "native_svg": 0, "native_gif": 0, "png_files": len(audits),
                  "report": str(ROOT / "测试报告.md"), "preview": str(ROOT / "实际返回PNG预览.jpg")}, ensure_ascii=False))
