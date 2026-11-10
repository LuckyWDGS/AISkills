# 异境、治愈与奇观参考库

合并快照：**2026-11-09，America/Los_Angeles**；本轮原始浏览记录是2026-11-10 UTC。包含2026-11-08基线及独立第二轮观测。标题为短摘录；今天采到不代表今天发布。

当前 **858个唯一作品条目：B32、C826、A0**。32条有实际画面采样，其中14条完成全程4fps联系表逐页检查，其余18条为历史单点/稀疏采样。14条共142页、6536张4fps样本，原帧补查另列；全库直接听审0，不称看完858条。

本轮8个主页659个作品卡，排除44条常规拍摄/剪辑教程，保留615条：575条新增、40条重复观察；新增8条密审（7用户种子＋1普通对照），61页/2809张。库内42个显示名、17个已记录规范主页、20条作者未充分建立是不同口径。

| 要回答的问题 | 入口 |
| --- | --- |
| 新7种子与普通对照实际发生什么、商业区间与结尾怎样核 | [第二轮八片拆解](wave2-studies.md) |
| 木米/云端/解忧/风铃的其他分支与孙空空/星星/Happy近邻 | [第二轮作者覆盖与对照](wave2-authors.md) |
| 原六条种子的密审与历史纠正 | [第一轮六条拆片](seed-studies.md) |
| 旧作者系列、照料/尺度/交通/停留等发散 | [第一轮作者](authors.md)、[母题](families.md)；均保留原快照范围 |
| 标签作品数与主页覆盖 | [当前标签观察](tags.md) |
| 全部来源、观测、实看页清单和批次 | [结构化数据](cases.json)、[检索脚本](../../scripts/search_cases.py) |

```powershell
python -X utf8 scripts/search_cases.py --summary
python -X utf8 scripts/search_cases.py --author 木米 --grade B
python -X utf8 scripts/search_cases.py --family 异境交通 --dense --layer finished_content_reference
python -X utf8 scripts/search_cases.py --role ordinary_control --dense
python -X utf8 scripts/search_cases.py --layer production_tutorial --summary
python -X utf8 scripts/search_cases.py --task stay --grade B
python -X utf8 scripts/search_cases.py --format three --grade B
python -X utf8 scripts/search_cases.py --freshness within_7_calendar_days --limit 8
python -X utf8 scripts/search_cases.py --id 7703009694587047204 --json
```

从Skill目录运行，`--limit 0`打印全部；筛选可组合。`--dense`只取已完成全程4fps实看的记录，`--role ordinary_control`找已登记普通对照，B级本身还包含稀疏采样。`--summary`默认各列最多20个作者/标签组，可用`--summary-limit 0`展开；总命中数不截断。`--layer`区分成片参考、其他系列、制作教程与旧待分记录。`--format/--task`只检索已建立的标签；没有标注不等于作品没有该功能。`families`多为标题层编辑分类，`actual_hashtags`才是采到的原标签，null不是无标签。

当前研究层：成片参考448、作者其他系列93、制作教程91、旧参考待分226。前448也包含仅元数据，不能称全都已看片。旧B级实片已归回成片参考，保留原有实看深度与日期；未重编码的具体格式仍待分。作者或教程自述的工具/关键词保持原主张，不能反推实际制作链。

## 日期与证据边界

以页面可核完整年月日重算：近7个日历日（11月3–9日）11条；近30日（10月11日–11月9日）另19条，合计30条；历史28；日期未核32；完全未知768。页面时区未知，按原展示日分组，不自行换时区。旧相对日期保留历史观察，不直接沿用为今天近期。带日期样本少，当前库不是近期爆款榜或全平台代表样本。

全程4fps仍可能漏短于采样间隔的事件。媒体hash、逐页实看与原帧补查分别记录；多人复核不加唯一作品或唯一源帧。没有后台曝光、留存、同龄分发或付费投流分母，不解释表现因果。

下一批优先补同用途/同周普通动态、声音直接听审、结尾与边界可信度。新批次应改变判断或缩小缺口，不按固定条数宣布充分。完整竞品媒体、签名资源地址与私有账号数据只留本地研究区。
