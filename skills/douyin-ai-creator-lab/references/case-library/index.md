# AI视频参考库

最新抖音批次观察日：**2026-11-12 UTC**（项目本地11月11日）。累计2454个唯一作品索引，B38/C2416；旧27个B站历史记录保持不变，本轮没有扩展其他平台。全库2481不能作为抖音分母。

当前市场研究优先读取日期可核的**近30日145条、近7日45条（已含在145内）**，覆盖41个规范主页、42个显示名；另1近期作品作者主页未建立。作品日期窗10月14日至11月12日，页面发布时间时区未知。130条成片参考、5条教程/工具主张、2条其他系列、8条AI来源未核的跨媒介视频，不能全称AI成片竞争对手。近月B27/C118，其中22部全程4fps，直接听审0。

全抖音库27部全程4fps（214页/9844张），另11部历史稀疏或单点。219条AI来源未核的邻近伴听、88条游戏解说、107条跨媒介图文、317条跨媒介视频单列；1233条为成片参考层，仍含未看动态的元数据。全库55个已记录规范主页；作品索引、近月、动态实看和来源已确认是不同分母。

| 要回答的问题 | 入口 |
| --- | --- |
| 本轮五种子、雨窗同日对照、夜林/微恐/梦核与热点语境 | [最新实片研究](evolution-studies.md)、[九主页扩展](evolution-authors.md)、[统计与来源](evolution-statistics.json) |
| 本轮近月话题、角色故事、标签、动态对照与重选方向 | [近月方向研究](month-topic-studies.md) |
| 怎样核当天热点与低播放、何时改方向 | [热点与作品表现复核](../trend-and-performance-review.md) |
| 官方课程实际读到什么、怎样转成检查项 | [课程实读与迁移](../official-course-learning.md) |
| 上一批1508索引、实时榜与类目周榜 | [增长研究历史快照](growth-studies.md)，分母与范围保留原批次 |
| 新七种子与普通对照、商业区间和结尾 | [第二轮八片拆解](wave2-studies.md)、[第二轮作者](wave2-authors.md) |
| 原六条种子与历史纠正 | [第一轮六条拆片](seed-studies.md) |
| 历史母题与作者系列 | [第一轮作者](authors.md)、[母题](families.md)；不是今日趋势 |
| 作品和主页双分母的原作标签 | [分批标签观察](tags.md) |
| 全部来源、观测、实看页和当前批次 | [结构化数据](cases.json)、[检索脚本](../../scripts/search_cases.py) |

```powershell
python -X utf8 scripts/search_cases.py --platform douyin --summary
python -X utf8 scripts/search_cases.py --platform douyin --as-of 2026-11-12 --freshness within_7_calendar_days --json --limit 0
python -X utf8 scripts/search_cases.py --platform douyin --as-of 2026-11-12 --freshness within_30_calendar_days_outside_7 --json --limit 0
python -X utf8 scripts/search_cases.py --platform douyin --author 拉k兔 --limit 8
python -X utf8 scripts/search_cases.py --platform douyin --tag 人类有自己的毛茸茸宇宙 --summary
python -X utf8 scripts/search_cases.py --platform douyin --dense --role ordinary_control
python -X utf8 scripts/search_cases.py --platform douyin --dense --format single_room --task stay
python -X utf8 scripts/search_cases.py --platform douyin --layer cross_medium --summary
python -X utf8 scripts/search_cases.py --platform douyin --id 7705436920582507826 --json
```

从Skill目录运行。近月完整集合取上述两个互斥时效查询结果，按platform/work_id做并集；本批为45＋100＝145作品，作者数需去重后另算。近7日属于近30日，不能再把45加到145上。`--limit 0`打印全部，`--summary-limit 0`展开全部作者/标签。`--as-of`只按完整年月日重新分窗，不联网、不推测年份或相对日期，也不刷新指标。历史45、日期未核23、未知2241均不进入本批当前市场结论。

`--dense`只取全程4fps实看；B还包含稀疏采样。`--role ordinary_control`只找明确登记角色，当前2条；比较候选和同作者作品不能自动升级为同龄同曝光控制实验。`--format/--task`只检索已经建立的分类，未标不等于没有。标题层分类不替代原作标签和动态事实。标签未知用null，已核无标签才用[]；主页粘连`#`候选不参与原标签统计。

这是可溯源的分层便利样本，不是全平台概率样本、当下爆款榜或算法规律。完整竞品媒体、签名资源与私人账号数据留本地。跨批重看不增加唯一作品数。
