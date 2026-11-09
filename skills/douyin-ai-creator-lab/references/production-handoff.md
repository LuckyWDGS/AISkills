# 制作交接与验收状态

本页是两个Skill之间唯一的交接与验收口径：douyin-ai-creator-lab写`pilot_brief`并负责验收记录；ai-video-prompt-director读入简报、交回`prompt_package`（格式见该Skill的`references/handoff-contract.md`）。其他参考只链接本页，不再各写一套。

```text
creator-lab：研究 → 方向 → pilot_brief
        ↓
prompt-director：参考计划 + 复制正文 → prompt_package
        ↓
执行方（用户或已授权的执行代理）：生成 → 原片
        ↓
creator-lab：review（requested / observed / retained / unresolved）→ 剪辑、复盘或回到director改一层
```

## pilot_brief：一个能试生的包

只填本次需要的字段；未知就写unknown，不为凑表编造。

```yaml
pilot_brief:
  brief_id: P-xxx
  scope: research_only / single_pilot / authorized_production   # 授权范围；研究不触发生成
  executor: user / agent        # 谁实际生成；agent需有本次明确授权
  viewer_promise: 观众这条能获得什么，下次还期待什么
  first_screen_hook: 首屏能读懂的对象、处境
  key_change: 一个值得等的变化（用途、结果、状态）
  ending: 可停留的结果或独立收尾
  duration: {requested: 用户要求或unknown, rationale: 由节拍决定，不照搬对标}
  subject_mode: character_drama / environment / object_event
  originality: {kept_function: 保留的观看功能, changed: 新对象/空间/任务/路线}
  assets:                       # 真正生成并看过的干净参考
    - id: ENV-xxx
      file: 本地路径（留项目，不进Skill）
      role: 唯一主要职责
      status: candidate / adopted_single_view / locked / superseded
      pixels: 实测宽×高；裁切或缩放另记
  geometry_status: single_view_only / cross_view_locked   # 单视域试生时镜头限制在可见范围
  sound_roles:
    world: 世界内环境与动作声
    voice: narration / dialogue / none
    music: 观众侧配乐或none
    capability: native / post_audio / unknown
  platform: h3 / seedance / muse_unknown / neutral
  generation_mode: 沿用用户当前偏好；首尾状态记录不等于硬首尾帧授权
  constraints: 无字、画幅、禁止项等用户明确要求
  fallback: 失败后怎样拆单元或改剪辑
  review_focus: 本条主要检验的一个问题
```

要点：

- 观看承诺、首屏、变化、结尾由节拍决定时长与镜数，不照搬对标数量。
- 固定环境需要一致的建立/反向/路线候选；只做单视角试验时写`single_view_only`，不称完整环境资产生产就绪。候选不是已锁定资产。
- 人审多格板、后加文字版与无字单视图分开；旧错误图、未选图和诊断视频标`superseded`，不混入上传集合。
- 请求2K或9:16不代表返回满足；裁切不等于原生分辨率。
- 声音分为世界内环境、旁白/对白、观众侧音乐；版本能力未核则`post_audio`。字幕后期；没有对白也可以成立，不为信息配额增加虚假行动。

## 完整提示词与分单元制作

- 只要完整提示词：主复制正文覆盖要求的完整时长；内部生产单元不能冒充主交付。可另列失败后的拆分方法；模型最长时长不足时说明限制并给剪辑方案。
- 委托制作成片：生产单元、原片可选时长与最终剪辑长度分别设计，按实际素材决定可用区间，不机械先抽整片或凑齐预估秒数。主交付是可播放的实际视频和简明复盘。

## review：按真实原片做记录

每个生产单元与最终成片都用四栏，不只写“成功/失败”：

| 字段 | 记录 |
|---|---|
| requested | 设计要求（来自prompt_package） |
| observed | 实际表现与查看范围（哪些时段、什么方式） |
| retained | 保留的区间及理由 |
| unresolved | 未满足的偏差、属于哪一层（参考/空间/动作/镜头/声音/语法）和下一步 |

“写了固定机位/末段停住”只是requested；能用剪辑去掉多余推进时保留原片和有效部分，但不称约束已满足。主体融化、因果不成立或身份错位不能靠裁短、叠化掩盖。一次只修最大问题，不因一条失败推翻全部资产。环境片的具体偏差表见prompt-director的环境片参考。

## 验收分层

拿到实际媒体后分层核验，每层只支持自己的结论：

| 层面 | 做什么 | 不能据此宣称 |
|---|---|---|
| 文件 | 实际尺寸、fps、帧数、时长、codec、音轨、大小/hash；完整解码 | 审美、语音或生成约束通过 |
| 画面 | 全片合理间隔采样＋关键变化＋末帧；切点附近加密，核源段映射 | 稀疏采样等于连续看完 |
| 运动与收尾 | 比较门窗/家具边缘、推近范围、雨汽变化、真正停止时刻 | 提示词写固定就等于输出固定 |
| 声音技术 | 音轨存在、峰值/响度、ASR与句界定位 | 听过、好听、音色一致或逐字准确 |
| 直接听审 | 实际可感知的语音/音乐/环境声及衔接，写覆盖范围 | 没听到的区间也通过 |
| 用户/平台 | 用户反馈与真实发布、后台指标分别记 | 技术通过等于用户认可或市场验证 |

- 短片可用约0.5秒间隔作概览、切点前后数帧加密；这是起点，不是配额。快速动作、短闪帧、可疑重复需更密或连续检查；接触图看不清就放大，不用自动差值指标代替看图。
- 没有直接听音能力时声音保持`listening_pending`，可以交试片并说明，不称全部验收通过。ASR近音词或原片/成片转写不同时标待听辨，不硬改成预期句子，也不据此判定错读。另一部已被认可的声音不移植到本片。
- 状态逐项分开：图片好看、模型成功、技术核验、直接听审、用户满意、作品发布、观众追更。网页显示完成、文件保存、面板打开、用户已看过也是不同状态。
- 用户只说“还可以”记总体认可，不扩大为每项声音通过、全系列锁定或发布授权。

## 首片反馈

首片交付后收集具体体验：是否想进入/留下、何处重复、哪次切换突兀、旁白是否舒服、结尾是否恰当。用户要先一集再决定其余时，后续集数等待这一步的决定。交付时说明改了什么、保留的偏差与下一条要验证的问题。
