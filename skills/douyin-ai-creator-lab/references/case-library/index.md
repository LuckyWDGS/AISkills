# 异境、治愈与奇观参考库

最新抖音快照：**2026-11-10，America/Los_Angeles**。抖音1508个唯一作品，B25/C1483；旧27个B站历史记录保留，本轮没有访问或扩展其他平台。全库1535不能作为抖音分母。

抖音中219条AI来源未核的邻近伴听单列；排除该层为1289条，仍含教程、其他系列和待分样本，不能全称AI成片竞争对手。921条为成片参考层，也不等于已看921条。

已做实际画面采样25条：14条完成全程4fps（142页、6536张），11条是历史稀疏／单点。全库直接听审0。本轮新增677唯一抖音作品、重观测211条；新增部分是元数据，没有新增全程密审。

| 要回答的问题 | 入口 |
| --- | --- |
| 最新热点、千条样本、普通对照与方向选择 | [2026-11-10增长研究](growth-studies.md) |
| 怎样核当天热点与低播放、何时改方向 | [热点与作品表现复核](../trend-and-performance-review.md) |
| 新七种子与普通对照、商业区间和结尾 | [第二轮八片拆解](wave2-studies.md)、[第二轮作者](wave2-authors.md)，均保留原批次日期 |
| 原六条种子与历史纠正 | [第一轮六条拆片](seed-studies.md) |
| 历史母题与作者系列 | [第一轮作者](authors.md)、[母题](families.md)；不是今日趋势 |
| 作品和主页双分母的原作标签 | [当前标签观察](tags.md) |
| 全部来源、观测、实看页和当前批次 | [结构化数据](cases.json)、[检索脚本](../../scripts/search_cases.py) |

```powershell
python -X utf8 scripts/search_cases.py --platform douyin --summary
python -X utf8 scripts/search_cases.py --platform douyin --as-of 2026-11-10 --freshness within_7_calendar_days --summary
python -X utf8 scripts/search_cases.py --platform douyin --author 几分好奇 --limit 8
python -X utf8 scripts/search_cases.py --platform douyin --family 奇观照料 --summary
python -X utf8 scripts/search_cases.py --platform douyin --dense --role ordinary_control
python -X utf8 scripts/search_cases.py --platform douyin --layer adjacent_ambience --summary
python -X utf8 scripts/search_cases.py --platform douyin --id 7706135635731500324 --json
```

从Skill目录运行。筛选可组合；`--limit 0`打印全部，`--summary-limit 0`展开全部作者/标签。`--as-of`只按完整年月日重新分窗，不联网、不推测年份或相对日期，不更新指标。近7日11月4–10日31条，近30日10月12–11月10日共77条（已含31条）；历史31、日期未核23、未知1377。平台时区未建立。

`--dense`只取全程4fps实看；B还包含稀疏采样。`--role ordinary_control`只找明确登记角色，当前只有1条；本轮7组比较候选另见`comparison_candidates_20261110`，没有将低计数卡自动升级为对照。`--format/--task`只检索已动态建立的标签，未标不等于没有。所有标题层分类都不替代原作标签和动态事实。

当前库是可溯源的分层便利样本，不是全平台概率样本、当前爆款榜或算法规律。完整竞品媒体、签名资源和私人账号数据留本地。跨批重复观看不增加唯一作品或源帧数。
