---
name: douyin-ai-creator-lab
description: Research Douyin and Bilibili AI-video works, authors' series, reference cases and tags; separate evidence from advertising; turn findings into original directions and pilot briefs; run authorized Muse generation, editing, voice-over repair and aspect-ratio adaptation; review real footage. Use for 抖音/B站AI方向、对标拆片、作者深挖、案例库、逐帧拆片、庇护所/梦核/奇观动作/异境列车研究、选题与封面、Muse制作与剪辑、竖改横、验片复盘. Not for writing or repairing the video prompt text itself (use ai-video-prompt-director) or for publishing (douyin-ai-publisher / bilibili-video-publisher / youtube-video-publisher).
---

# 抖音与B站AI创作实验室

把「喜欢这条，想学着做」转成有证据的观察、自己的观看承诺、可试生的小样和下一条决策。AI是制作方式；栏目要让观众知道下次还值得看什么。不要从一条爆款直接替用户永久定赛道。

## 分工

- **本Skill管**：研究与证据、原创方向、`pilot_brief`、已授权的Muse生成与剪辑、配音返修、画幅适配、验片记录与复盘。
- **ai-video-prompt-director管**：动作、空间、参考职责、声音归属、镜头衔接和复制提示词。本Skill把`pilot_brief`交给它，拿回`prompt_package`。
- **发布Skill管**：已确定成片的上传与提交。
- 交接格式与验收口径只有一处：[制作交接与验收状态](references/production-handoff.md)。

## 路由

| 用户想做什么 | 读取 / 运行 | 交付 |
|---|---|---|
| 对标、主页、相似作者、广告筛除、跨平台比较、为什么高赞 | [案例研究](references/case-study-method.md)；音效/BGM按其声音字段；要求不打扰时按后台研究方式 | 可见证据 → 可能机制 → 反例/未知 → 原创试法 → 观察指标 |
| 给了喜欢的作品，要更多样本或深挖作者 | [作者系列与原创转译](references/author-series-and-transfer.md)；先查[案例库](references/case-library/index.md)，再补会改变判断的新样本 | 作者卡、对照、发散方向；不只解释用户给的几条 |
| 按作者/方向/标签/证据找已有案例 | `python -X utf8 scripts/search_cases.py --summary`，按需加`--author/--family/--tag/--grade/--query/--id` | 命中列表；快照不代表当前热度 |
| 批量拆片、并行研究、维护案例库、沉淀方法 | [研究执行与证据复核](references/research-execution-and-review.md) | 时间轴记录、实看范围、可重算的汇总 |
| 作品时长、镜头约数、每房节奏 | [时长与镜头核查](references/duration-and-shot-analysis.md) | 作者—作品—时长—镜数表＋对自己方案的影响 |
| 每秒3–5帧、逐帧拆解、关键切点复核 | [密采样方法](references/duration-and-shot-analysis.md#每秒35帧的密采样)，默认4fps并逐页实看 | 产表与实看记录分别登记 |
| 原作标签、标题机制、准备接发布 | [标签与发布交接](references/tags-and-release-handoff.md) | 实际标签 / 研究分类 / 建议标签 / 当天热点分列 |
| 资料够不够、题材评分、封面比较 | [选题与封面评审](references/topic-selection-and-covers.md) | 公开权重的评分、实际生成并看过的封面 |
| 不知方向、首片、小样包、实片复盘 | [小样与反馈](references/pilot-and-feedback.md) ＋ [制作交接](references/production-handoff.md) | `pilot_brief`；或review四栏与下一条只改什么 |
| 实际生图 | 当前可用的图像Skill（已装image-generation-director/cm-imagegen时沿用用户路由偏好） | 真实图片；工具不可用时交制作简报并说明图未完成 |
| 写视频提示词 | ai-video-prompt-director及当次平台适配器 | `prompt_package` |
| 已授权用Muse生成、剪辑或修片 | [Muse制作与剪辑](references/muse-production-and-editing.md) | 真实媒体＋独立核验 |
| 已有成片改画幅 | [尺寸与导出](references/muse-production-and-editing.md#尺寸与导出陷阱) | 按用户选定的保留画面、裁切或重做路线 |
| 工具或媒体出现异常（抓帧、FFmpeg、TTS、上传） | [已知陷阱](references/known-pitfalls.md) | 症状 → 核查 → 处理 |
| 发抖音 / B站 / YouTube | douyin-ai-publisher / bilibili-video-publisher / youtube-video-publisher；需横版先在本Skill适配并验片 | 交接给发布Skill |

平台：用户未明确且没有有效持续偏好时只问一次。已选Muse而底层模型未显示时，沿用平台无关中文导演稿并记模型unknown，不反复要求在H3/Seedance间二选一。

## 研究到小样

1. **定位**：从用户作品找原链接与作者，记录平台、地区、作品日期、观察日期和查看范围。分享口令日期不是发布日期。
2. **扩样**：沿原作者其他系列、同类普通作品、近期作品和相邻作者扩展，分开作者固定承诺与每集变化；优先补可核日期、能检验假设的对照。按唯一作品ID去重，分离作品、推荐线索与广告卡；数量不能代替观看质量，推荐或自动连播不算完整观看。新抓取不等于新发布，旧作与日期不明的卡片不进当前趋势结论。
3. **标证据等级**：每条写明是完整视听、无声画面采样、仅元数据还是检索线索。没听到声音就不写曲名、对白、配器或听感；没看动态就不写完整运镜。
4. **建假设**：用实际首屏、变化、切点、结尾与观众表达建立假设。高赞与普通都有的特征只是风格共性；播放、完播、投放和粉丝规模不可见就保持未知。
5. **原创方向**：先写观众能获得什么，再提少量差异清楚的方向；保留原作的功能性经验，改变具体空间、视觉母题、文案、节拍或进入方式。不逐帧复刻，不换个提示词就称原创。
6. **静态候选**：生成少量原创静态候选帮助定方向；用户已授权采用导演审美时沿用该决定。风格采用不等于未知视角几何已锁定。
7. **pilot_brief**：补本次需要的空间/身份资产，按[制作交接](references/production-handoff.md)写`pilot_brief`，交ai-video-prompt-director出`prompt_package`；同时写声音与后期计划和失败退路。
8. **执行与验片**：按当前分工由用户或执行代理取得实际视频，按review四栏验片、剪辑和交付。原片长度、计划片长、实际成片时长分开记；依实际内容去重，不用空镜或冻结补足设计时长。先做一集再评估时，到该集交付和反馈为止；发布另按当前明确指令执行。

## 交付与判断

交付让用户立即知道：建议先做什么、证据支持到哪里、下载哪张干净参考、复制哪段正文、怎样生成、成片怎样交回。只要完整提示词时，主提示词覆盖要求时长；要求代做成片时，主交付是可播放的实际视频和简明复盘。文字多不代表完成，提了生图方案也不等于已有图片。

「为什么爆」写成 **可见证据 → 可能观看机制 → 反例/未知 → 原创试法 → 观察指标**。梦核可能同时带来向往、熟悉、孤独、不安与晕眩，不一律包装成治愈。不把用户或作者自述的限流当平台事实，不承诺流量池、必火标签或固定收益。

素材QA和市场验证是不同状态，逐项见[验收分层](references/production-handoff.md#验收分层)。视频仍由用户操作时不代提交；用户已明确授权某路线生成与剪辑时不重复确认同一分工，也不自动恢复其他暂停路线。用户未要求监控时不建立自动复盘或定时发帖。

## 沉淀与项目边界

在项目中先读AGENTS/CLAUDE和当前进度。用户要求沉淀样本时，可将有出处、观察日期和证据范围的公开案例摘要纳入按需读取的案例库；完整竞品媒体、签名资源地址、原始网络请求、私有账号数据与发布记录留本地项目。

研究或验片得到经过实际验证、可迁移的新方法时，补入对应参考或工具并连接入口：先查重，写明适用条件、已知失败和复核方式。一次性工具故障写进[已知陷阱](references/known-pitfalls.md)，按“症状 → 核查 → 处理 → 适用范围”格式，不混进主流程。案例事实、待验证创意和通用方法分别保存，不把一次成功扩成所有题材的硬规则，也不把一个项目的画风、每镜时长或声音选择变成通则。
