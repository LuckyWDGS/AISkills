# 页表数据与 QA 脚本

三个脚本位于 `scripts/`，只依赖 Pillow（`pip install -r requirements.txt`），在本地无头运行，不操作浏览器。产物写在内容项目里；脚本源码不随作品复制。

| 脚本 | 作用 |
| --- | --- |
| `story_manifest.py` | 从图片目录生成页表骨架；校验页表与文件 |
| `compose_bubbles.py` | 按页表把中文对白/旁白合成到无字底图上，输出成品页和排版报告 |
| `qa_preview.py` | 联系表、390px 窄屏预览与阅读页、局部上下文截图、机械检查、哈希与版本对比 |

脚本只完成可重复的机械工作并留下证据。肢体结构、气泡是否指对人、动作因果和标题兑现，仍须按 [人物动作、气泡与透明度复核](visual-qa.md) 查看实际图片；报告“无错误”不等于视觉验收通过。

## 页表 `story_manifest.json`

路径相对页表文件；`box` 为 `[x, y, w, h]`，`tail` 为 `[x, y]`，均是 0–1 的相对坐标，换分辨率仍有效。

```json
{
  "schema": "wechat-story-manifest/1",
  "title": "退租时我拆了窗帘，房东不让了",
  "settings": {"reading_width_px": 390, "max_pages": 20, "min_reading_font_px": 13,
               "max_reading_font_px": 18, "min_contrast": 4.5, "fill_alpha": 160},
  "watermark_zones": [[0.6, 0.93, 0.4, 0.07]],
  "pages": [
    {
      "id": "p01",
      "base": "base/p01.png",
      "image": "pages/p01.png",
      "note": "state_before → visible_action → state_after",
      "bubbles": [
        {"speaker": "小林", "text": "退租那天，我把窗帘拆下来装进了袋子里。",
         "box": [0.05, 0.05, 0.5, 0.18], "tail": [0.28, 0.42]},
        {"speaker": "房东", "kind": "offscreen", "text": "（电话）那窗帘是房子带的吧？",
         "box": [0.5, 0.3, 0.45, 0.14], "tail": [0.9, 0.52], "shape": "ellipse"},
        {"kind": "caption", "text": "三年前，我自己买的。", "box": [0.05, 0.86, 0.55, 0.07]}
      ],
      "review_regions": [
        {"label": "小林双手与袋子", "box": [0.15, 0.45, 0.35, 0.3]},
        {"label": "小林脸", "box": [0.18, 0.3, 0.2, 0.15], "avoid": true}
      ]
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `base` / `image` | 无字底图与最终成品页；二者必须不同，底图从不被覆盖。没有 `base` 的页视为已成品，只参与 QA。 |
| `bubbles[].kind` | `speech`（须有 `speaker` 与 `tail`）、`thought`（尾巴画成小圆点）、`caption`（旁白框，无尾巴）、`offscreen`（画外音/电话，在文字里写明来源）。 |
| `bubbles[].tail` | 尾巴尖端位置：由看过画面的人或模型指向说话人头部附近，脚本不识别人物。确实不需要尾巴时写 `"no_tail": true`。 |
| `shape` | `round`（默认）、`ellipse`、`rect`（旁白默认）。 |
| `font_px` | 指定字号（原图像素）；不写则自动适配，同一页同类气泡统一为最小适配字号，并限制在阅读宽度下 13–18px。 |
| `fill_alpha` | 气泡底色不透明度 0–255；160 约为 63% 不透明。只是起始值，按背景逐框调整。 |
| `review_regions` | 需要放大复核的区域（手、道具、交接点、脸）；`avoid: true` 时气泡压到它会告警。 |
| `watermark_zones` | 平台发布水印的避让区，按当前平台预览确定，不照搬旧坐标。 |

## 标准流程

```powershell
$S = "<skill>/scripts"
python $S/story_manifest.py init --base-dir base --pages-dir pages --out story_manifest.json --title "发布标题"
# 按页表补 bubbles / review_regions，然后：
python $S/story_manifest.py validate --manifest story_manifest.json
python $S/compose_bubbles.py --manifest story_manifest.json --save-overlay
python $S/qa_preview.py --manifest story_manifest.json
```

修改单页后：`compose_bubbles.py --pages p05`，再完整运行一次 `qa_preview.py`。

## 输出与解读

`compose_bubbles.py`

- 成品写入 `image`；内容变化时旧版保存在 `pages/_versions/<id>-<旧哈希前8位>.png`，内容未变则不重写。`--save-overlay` 另存气泡层到 `_overlays/`。
- 报告 `qa/compose-report.json`（部分页运行时与其他页记录合并）：每个气泡的行、字号、阅读宽度下字号、填充不透明度、背景均值/纹理、最低对比度、告警。
- 错误（不写文件，退出码 1）：文字溢出、缺底图、含中文却找不到中文字体。告警：`low_contrast`、`textured_background_shows_through`（背景花纹透出）、`overlaps_watermark_zone`、`covers_avoid_region:*`、`bubbles_overlap`、`tail_inside_bubble`。
- 透明实现：气泡框和尾巴共用一个蒙版一次合成，外框沿合并轮廓描边；文字最后以不透明颜色绘制。最终 PNG 可能是 RGB，但已合成的半透明效果仍在。
- 字体：页表 `font` 或 `--font` 优先，否则依次查找 Noto Sans SC、思源黑体、微软雅黑、黑体及 macOS/Linux 常见中文字体；报告记录实际使用的字体。

`qa_preview.py`（默认输出到 `qa/`）

- `contact-sheet.png`：全篇顺序、页码与短哈希，用于看整体节奏与连续性，不能代替逐页检查。
- `narrow/<id>.png`、`narrow/strip-NN.png`：按阅读宽度（默认 390px）缩放的单页和连续长图；`reader.html` 以 390px 栏宽显示原图。均为本地模拟，不是实体手机测试。
- `crops/`：每个气泡与复核区域带上下文的局部图，从当前成品重新截取，只缩小不放大。
- `qa-report.json` 的 `check`：页数是否超过上限、文件缺失/损坏、尺寸或比例不一致、合成报告是否与当前文件哈希匹配（不匹配说明页面在合成后被改过，字号/对比度结论失效）、末页是否有“本篇完/未完待续”。
- `hashes.json` 与 `hashes.prev.json`：与上次运行比较，`recheck` 列出改动页及其相邻页。旧的审读结论不适用于这些页，须重新查看。

复核记录写明所查看的 `hashes.json` 时间与页面哈希，结论只对应这些文件。
