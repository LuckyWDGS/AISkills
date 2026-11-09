import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
labels = {"square": "方图：只改变 size", "landscape": "横图：只改变 size", "portrait": "竖图：只改变 size",
          "gif": "GIF 动画", "svg": "SVG 矢量", "square_prompt": "方图：加入明确构图提示", "portrait_prompt": "竖图：加入明确构图提示"}
rows = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
extra = ROOT / "prompt-shapes" / "results.json"
if extra.exists():
    rows += json.loads(extra.read_text(encoding="utf-8"))

table_rows, cards, previews, md_rows = [], [], [], []
for row in rows:
    result = row["result"]
    name = labels.get(row["case"], row["case"])
    actual = ", ".join(result.get("output_dimensions", [])) or "未返回可读文件"
    formats = ", ".join(str(x.get("format")) for x in result.get("media_outputs", [])) or "—"
    shape = "—"
    if row["requested_format"] == "png" and result.get("output_dimensions"):
        ew, eh = map(int, row["requested_size"].split("x"))
        aw, ah = map(int, result["output_dimensions"][0].split("x"))
        shape = "匹配" if abs(aw/ah - ew/eh) < 0.001 else "不匹配"
    status = "通过" if result.get("ok") else "未通过"
    preview_status = "画幅匹配，像素不符" if shape == "匹配" and not result.get("ok") else status
    summary = f'{row["requested_size"]} / {row["requested_format"]} → {actual} / {formats}'
    table_rows.append(f'<tr><td>{html.escape(name)}</td><td>{html.escape(row["requested_size"])}</td><td>{html.escape(row["requested_format"])}</td><td>{html.escape(actual)}</td><td>{html.escape(formats)}</td><td>{shape}</td><td class="{"pass" if result.get("ok") else "fail"}">{status}</td></tr>')
    md_rows.append(f'| {name} | {row["requested_size"]} / {row["requested_format"]} | {actual} / {formats} | {shape} | {status} |')
    media = []
    for path_text in result.get("paths", []):
        path = Path(path_text)
        rel = path.relative_to(ROOT).as_posix()
        info = next((x for x in result.get("media_outputs", []) if x.get("path") == path_text), {})
        if info.get("readable"):
            media.append(f'<a href="{html.escape(rel)}" target="_blank"><img src="{html.escape(rel)}" alt="{html.escape(name)}"></a>')
            if info.get("format") != "svg":
                previews.append((name, summary, path, preview_status))
        else:
            media.append(f'<a href="{html.escape(rel)}" download>下载返回原始文件</a>')
    warnings = result.get("size_validation_warnings", []) + result.get("media_validation_warnings", [])
    detail = result.get("error") or json.dumps(warnings, ensure_ascii=False, indent=2) if not result.get("ok") else "文件格式与请求尺寸检查通过。"
    cards.append(f'<article><h2>{html.escape(name)}</h2><p>{html.escape(summary)}</p>{"".join(media)}<details><summary>核查结果 · {row["elapsed_seconds"]} 秒</summary><pre>{html.escape(str(detail))}</pre></details></article>')

intro = "本轮使用 gpt-image-2.6-sunburst，quality=max、complexity=high，同一网关。每个案例只提交一次。前三个案例提示词完全一致，仅改变 size；追加案例单独检验明确画幅提示词。所有原图保持服务返回字节，未裁剪、缩放或转换格式。"
findings = "仅改变 size 的三次请求均返回 1536×1024。明确写 1:1 后返回 1254×1254 方图；明确写 2:3 竖版后返回 1024×1536，符合目标。GIF 被当前请求通道以 HTTP 400 拒绝：尚未启用；SVG 请求实际返回 PNG，未获得矢量文件。"
body = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>cm-imagegen 参数与画幅验证</title><style>
body{{margin:0;background:#eef2f5;color:#172435;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1400px;margin:36px auto;padding:0 24px}}h1{{font-size:32px;margin:0}}.intro{{max-width:1050px;color:#415366}}table{{border-collapse:collapse;width:100%;background:white;margin:24px 0}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #e1e8ee}}th{{background:#172435;color:white}}.pass{{color:#15764f;font-weight:700}}.fail{{color:#a5472a;font-weight:700}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:22px}}article{{background:white;border-radius:12px;padding:20px}}h2{{font-size:20px;margin:0 0 8px}}article p{{font-size:14px;color:#526275}}img{{display:block;max-width:100%;height:430px;object-fit:contain;margin:auto}}pre{{font:12px/1.6 monospace;white-space:pre-wrap;overflow-wrap:anywhere}}details{{margin-top:12px}}.scroll{{overflow-x:auto}}@media(max-width:600px){{main{{padding:0 14px}}.grid{{grid-template-columns:1fr}}img{{height:auto;max-height:500px}}}}
</style><main><h1>参数与画幅验证</h1><p class="intro">{html.escape(intro)}</p><p>{html.escape(findings)}</p><p>已接入 GIF/SVG、标注编辑、压缩、流式及相应校验。客户端支持与网关实测支持分别记录。</p><div class="scroll"><table><thead><tr><th>案例</th><th>请求尺寸</th><th>请求格式</th><th>实际尺寸</th><th>实际格式</th><th>画幅比例</th><th>精确尺寸/格式</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div><section class="grid">{"".join(cards)}</section><p>点击图片打开未加工原图。具体请求和 CLI 输出保存在各案例目录的 request.json / stdout.json / stderr.txt。</p></main></html>'''
(ROOT / "检查画廊.html").write_text(body, encoding="utf-8")
md = "# cm-imagegen 参数与画幅实测\n\n" + intro + "\n\n" + findings + "\n\n| 案例 | 请求 | 实际返回 | 画幅比例 | 精确尺寸/格式 |\n|---|---|---|---|---|\n" + "\n".join(md_rows)
md += "\n\n客户端已加入：GIF 帧数/时长、SVG 与可选作者模型、markup 标注编辑、压缩、流式预览参数、审核级别及匿名用户标识。SVG 编辑因官方文档不一致暂未启用。默认不再发送旧 response_format。\n\n77 项离线测试通过，技能结构校验和 diff 空白检查通过。该结果不证明网关透传了所有参数，也不证明真实上游模型身份；实测只依据收到的文件。\n"
(ROOT / "检查报告.md").write_text(md, encoding="utf-8")

if previews:
    font_path = "C:/Windows/Fonts/msyh.ttc"
    font = ImageFont.truetype(font_path, 22)
    small = ImageFont.truetype(font_path, 16)
    cols = 3
    cell_w, cell_h = 500, 430
    sheet = Image.new("RGB", (cols*cell_w, ((len(previews)+cols-1)//cols)*cell_h), "#eef2f5")
    draw = ImageDraw.Draw(sheet)
    for index, (name, summary, path, status) in enumerate(previews):
        x, y = (index % cols)*cell_w, (index // cols)*cell_h
        draw.text((x+18,y+14), name + " · " + status, font=font, fill="#172435")
        draw.text((x+18,y+50), summary, font=small, fill="#526275")
        with Image.open(path) as im:
            thumb = ImageOps.contain(im.convert("RGB"), (464,338))
            sheet.paste(thumb, (x+(cell_w-thumb.width)//2,y+82+(338-thumb.height)//2))
    sheet.save(ROOT / "画幅实测预览.jpg", quality=92)
print(json.dumps({"cases":len(rows), "gallery":str(ROOT / "检查画廊.html"), "report":str(ROOT / "检查报告.md")}, ensure_ascii=False))
