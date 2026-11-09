# 异境、治愈与奇观参考库

快照：2026-11-08，America/Los_Angeles。案例用于分析与原创试验。标题均为短摘录，数据与链接随时间变化；今天收入库不代表今天发布。

当前有 **283个唯一作品条目**：B级24、C级259，A级0。B级包含历史单点/稀疏采样；其中6条完成每秒4帧全程接触表逐页检查，详情见[六条重点拆片](seed-studies.md)。没有完整有声观看；不把283条写成看完283条。

37个已记录作者显示名并不等于已核独立作者数，另有20个作品作者归属未充分建立。四位主要显示名的记录数：𝘼𝙞𝙨𝙢𝙧 75、非梦59、云端避风港-Dream Shelter36、AI.814 21。云端别名历史记录保留，不因名字相似自动并号。

| 要回答的问题 | 读取入口 |
| --- | --- |
| 六个用户种子实际发生什么、镜头怎样接、有什么适配限制 | [重点拆片](seed-studies.md) |
| 作者还能反复做什么、其他作品与普通计数对照 | [作者系列](authors.md) |
| 从庇护所发散到照料任务、尺度、物件操作、异境交通与停留 | [母题与案例](families.md) |
| 原作实际用了哪些标签，如何避免把频次当流量公式 | [原始标签观察](tags.md) |
| 查具体ID、全部来源与历次观察 | [可检索数据](cases.json)和[搜索脚本](../../scripts/search_cases.py) |

```powershell
python -X utf8 scripts/search_cases.py --summary
python -X utf8 scripts/search_cases.py --author 非梦 --limit 8
python -X utf8 scripts/search_cases.py --family 天象照料
python -X utf8 scripts/search_cases.py --tag 地铁
python -X utf8 scripts/search_cases.py --id 7697951559430278454 --json
```

从Skill目录运行；默认只打印少量匹配，`--limit 0`会打印全部。研究分类是编者标注；`actual_hashtags`才是实际采到的作者标签，null表示没采到，不能按无标签解释。每条新证据保留观察日期、方法和范围，不倒写历史C级为早就看过。

## 证据与缺口

全程4fps是每秒3–5帧要求下的时间采样，关键疑点另回原帧率；不是查看原片所有24/30/60fps帧，更不是直接听审。案例库没有经过完整视听的A级样本，也没有竞品后台曝光、留存、付费合作和投流分母，不能解释播放差异的因果。

日期分组：{"within_30_days_by_display_date": 12, "historical_by_display_date": 8, "within_7_days_by_display_date": 4, "unknown": 227, "year_or_date_unverified": 23, "within_7_days_by_relative_date": 6, "within_30_days_by_relative_date": 3}。这是按快照日与页面日期的内部研究分组；页面时区未知不自行换算，月日缺年保留未核。历史、日期不明和商业内容不并称当前自然热点。

下一轮扩样优先补会改变判断的缺口：同作者同母题的普通作品动态、可核近期作品、声音直接听审及结果/结尾，不以凑新的数量为目标。完整竞品媒体、签名资源地址、私有文件路径和后台数据不在此库。
