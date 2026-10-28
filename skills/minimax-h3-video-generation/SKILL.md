---
name: minimax-h3-video-generation
description: "PAUSED: MiniMax-H3 video-generation automation is retained for future revision but must not be invoked, run, or used for API calls, uploads, polling, downloads, or archiving until the user explicitly re-enables it."
metadata:
  status: paused
  paused_on: "2026-08-18"
---

# MiniMax H3 视频生成

> **当前状态：`paused`（2026-08-18 起）**
>
> 用户已明确要求暂时不要使用自动化 Skill。保留本文件、脚本和参考资料，但在用户明确说“重新启用自动化”之前，不得调用本 Skill，不得运行其 CLI，不得自动上传参考，不得调用视频生成 API，也不得执行 `prepare`、`submit`、`run`、`poll`、`download`、自动重命名或自动归档。普通剧本、分镜、全模态参考规划、提示词编写和用户生成后的人工 QA 继续使用项目级规则完成。
>
> 下文是未来恢复前的历史设计记录，不是当前可执行流程。若用户只说“生成视频”“继续下一段”或“生成提示词”，不要据此恢复自动化；只有明确的重新启用决定才进入恢复评估。

这个 Skill 把“分镜已确认”与“实际消耗额度的 API 调用”分开：先生成可审阅的请求预览，只有用户明确确认同一份预览后，才能提交。提交后可自动轮询、下载、重命名、写入无密钥素材清单，并提取真实尾帧作为下一段首帧来源。尾帧默认同时保留原始事实帧和一个非生成式的轻度增强副本，方便上传与人工检查。

## 安全与默认值

- 本项目的导演/适配默认模式是 `multimodal_reference`：使用必要的 `reference_image`、`reference_video`、`reference_audio` 作为不同职责的参考，硬 `first_frame/last_frame` 仅在用户对该次请求明确选择时启用。分镜里的起始状态、结束状态和稳定尾帧是连续性合同，不自动等于 API 硬首尾帧参数。
- 绝不把 API key 写入 Skill、项目、预览、任务记录、日志或 Git，也不接受 `--api-key` 命令行参数。默认从 `METASO_MINIMAX_API_KEY` 读取；通过本机密钥管理器或当前终端设置环境变量。
- 用户在对话中展示过的 key 视为已暴露，正式生成前提醒用户轮换；不要在回复或命令输出中复述它。
- 默认创建地址为 `https://metaso.cn/api/minimax`，查询地址默认跟随创建地址；如代理不提供查询接口，使用 `--query-base-url https://api.minimaxi.com`。
- 默认模型为 `MiniMax-H3`、分辨率为 `768P`、比例为 `9:16`、时长为最短的 `4` 秒。需要正式的 15 秒段时显式传 `--duration 15`，不要把测试时长当成成片时长。
- 本地参考文件只在提交时按官方大小上限转换为 data URI；大文件使用公网 URL 或已上传的 `mm_file://{file_id}`。不擅自把本地素材上传到未确认的第三方服务。
- 生成前先读取当前分镜的“角色与参考图”和 `00_人物设定/人物锁定.md`。对本段实际出现或需要生成身份的角色，使用 `--character programmer`、`--character boss` 等参数加入项目锁定图；未出场的女性 HR 不上传。也可以用 `--character-reference character_id=路径` 加入自定义角色图。
- 尾帧增强默认使用 Pillow 做 `2× Lanczos` 放大和轻度 `UnsharpMask`（半径 `0.8`、强度 `35`、阈值 `3`）。这是插值与锐化，不会恢复真实不存在的细节，也不使用生成式“补脸”；原始 `*-F-actual.png` 永远保留且不被覆盖。需要该功能时本机应安装 `Pillow`：`python -m pip install Pillow`。

## 强制工作流

### 0. 导演包空间与动作预检（不联网）

在运行 `prepare` 前，先读取项目的 `skills/ai-video-prompt-director/SKILL.md`、`我的表述/04_进度管理/AI镜头可生成性与风险清单.md`、`我的表述/04_进度管理/空间调度与连续动作规范.md` 和 `我的表述/04_进度管理/视觉资产锁定与三视图规范.md`。只有导演包满足以下条件，才进入请求预览：

- 当前生成单元只有一个主要空间、一条镜头路径和一条连续动作链；
- `generation_mode` 默认为 `multimodal_reference`；已在提示词代码块外选出唯一 `dominant_spatial_anchor` 和最小参考集合，每份场景/角色/对象/动作/风格/音频参考只有一个主要职责；
- 已检查 scene × character、scene × object、character × action、object × action、style × facts、audio × visual identity 的竞争；多格图文板、带文字参考和重复定义同一主体/空间的素材已删除或裁净；
- 本段新增的长期角色、固定场景、车辆或关键物体已有候选/已锁定套图、稳定 ID 和干净单视图；候选状态已明确，未把 AI 推断的真实地点/物体未知角度当作事实，也没有把多格人审板直接作为默认视频参考；
- 已填写固定参照、镜头朝向、轴线、屏幕位置、深度、身体朝向、视线目标和对象路线；
- 每句对白有唯一说话人、听话人和声源区域；画外对白没有被误写成内心独白；
- 汽车、三轮车、手机、文件等对象各有独立数量、固定/移动状态和结束位置；碰撞/消失已拆为前状态、过程和结果；
- 15 秒使用“意图 → 准备 → 执行 → 可见结果 → 反应/下一决定”的动作脊柱，最后至少 1.5 秒稳定；
- 每个可见边界已标记 `same_frame_handoff`、`match_on_action`、`planned_cut` 或 `cutaway_insert`；只有用户明确选择硬首尾帧时才检查端点插值兼容性。

这一步不增加 API 字段，也不把项目管理说明塞进模型提示词；它只阻止存在空间歧义、车辆融合、对白目标错位或长时间无信息停留的导演包进入 `prepare`。当前项目仍由用户执行视频生成，Codex 未获新授权时只停在提示词、参考映射和 QA 阶段。

### 1. 生成预览（不联网、不读取 key）

使用脚本 `scripts/minimax_video_cli.py`：

```powershell
python scripts/minimax_video_cli.py prepare `
  --prompt-file "E:\path\SEG03-prompt.txt" `
  --project-root "E:\MyJuBen" `
  --character programmer `
  --character boss `
  --reference-video "E:\path\SEG02-actual.mp4" `
  --reference-audio "E:\path\voice.mp3" `
  --duration 4 --resolution 768P --ratio 9:16 `
  --segment-id SEG03 `
  --output "E:\path\SEG03-preview.json"
```

`prepare` 会输出提示词、参考素材路径/URL、文件摘要、接口地址、模式和全部参数，并给出 `preview_sha256`。它不读取 key、不发请求。默认只传经过全模态预检的最小 `reference_image/video/audio` 集合；只有用户明确选择硬首尾帧时才使用 `--first-frame` / `--last-frame`，并遵守其不能与 `reference_image/video/audio` 混用的接口规则。

### 全模态默认与硬首尾帧例外

先根据分镜决定承接优先级，再生成预览：

- **默认 `multimodal_reference`**：先选一份主空间锚点，再按缺失事实加入当前可见且身份关键的角色图、必要对象图、动作/视频参考和独立音频参考。提示词正文聚焦运动、互动、视线、路线和结果；语义参考表、路径、哈希及临时绑定留在正文外。
- **上一段尾帧作为普通连续性参考**：需要参考上一段状态但仍要角色图/音频/视频时，把尾帧作为 `--reference-image`，不要传 `--first-frame`。它是软参考，不保证像素级第一帧，也不得与另一张场景图共同争夺主空间；若新场景已计划内剪切，尾帧可以不上传。
- **角色身份补充**：只有当前可见、身份关键且未被主锚点可靠锁定的角色才使用 `--character programmer --character boss`。它们会作为 `reference_image` 进入 API；老板只画外发声时不上传老板图，女性 HR 未出场时不上传。
- **动作、对象、风格与音频**：只在缺少该职责时加入。动作参考不负责脸和空间，对象参考不负责摆位，风格参考不负责剧情事实，声音参考不负责生成可见人物。若某份参考同时抢占多个职责，先裁切或删除。
- **明确选择硬首尾帧**：只有用户明确要求下一段第一帧必须等于某真实帧，或明确要求首尾帧插值，才使用 `--first-frame` / `--last-frame`。MiniMax-H3 当前接口禁止它与 `reference_image/video/audio` 同时出现；CLI 会拒绝硬首帧与 `--character`/`--character-reference` 混用。
- **互斥取舍**：如果用户明确需要硬帧又希望使用角色/视频/音频参考，必须展示两种模式的取舍并重新确认，不能为了同时塞素材而违反接口互斥规则。

`--character` 会从项目根目录的 `我的表述/00_人物设定/参考图/` 解析：`programmer → 程序员_参考.png`、`boss → 老板_参考.png`、`hr → 女性HR_参考.png`。预览和无密钥任务摘要会保留 `character_id`、路径和 SHA-256；提交给 API 的字段仍是标准 `reference_image`，不会把本地路径或额外私有字段发给接口。

### 2. 让用户审阅并确认

在 Codex 对话中展示最终提示词、参考素材、模型、比例、分辨率、时长、创建/查询地址、警告和预览 SHA-256。明确询问用户是否按这份预览生成。没有明确确认时，不运行 `submit` 或 `run`。

用户确认后只提交同一份预览，并同时传入 `--confirm` 与预览时打印的 `--confirm-sha256`。如果提示词、参考文件、参数或文件内容有任何变化，重新运行 `prepare`，不要复用旧 hash。

### 3. 提交、轮询和归档

一步完成的安全调用：

```powershell
$env:METASO_MINIMAX_API_KEY = "（在本机安全设置，不要写入项目）"
python scripts/minimax_video_cli.py run `
  --request "E:\path\SEG03-preview.json" `
  --confirm --confirm-sha256 "<prepare 输出的 SHA-256>" `
  --record-dir "E:\path\task-records" `
  --archive-dir "E:\MyJuBen\我的表述\02_分镜\素材\EP01_SC01_SEG03" `
  --segment-id SEG03
```

`run` 会：提交 `POST /v2/video_generation` → 按 `queued/running/succeeded/failed/cancelled` 轮询 → 下载成功响应中的限时 `content.url` → 保存 `SEG03-actual.mp4` → 提取 `SEG03-F-actual.png` → 默认生成 `SEG03-F-enhanced-2x.png` → 写入 `SEG03-manifest.json`。任务记录和清单只保存请求摘要、task id、响应、路径、哈希和媒体信息，不保存 key 或本地文件的 data URI。关闭增强可传 `--no-enhance-tail`；调整倍率可传 `--tail-scale`，文件名和 manifest 会记录实际倍率。

需要分步恢复时使用：

```powershell
python scripts/minimax_video_cli.py submit --request PREVIEW.json --confirm --confirm-sha256 HASH --record-dir TASKS
python scripts/minimax_video_cli.py poll --record TASKS\task-ID.json
python scripts/minimax_video_cli.py download --record TASKS\task-ID.json --archive-dir OUT --segment-id SEG03
python scripts/minimax_video_cli.py extract-tail --video OUT\SEG03-actual.mp4 --output OUT\SEG03-F-actual.png --enhanced-output OUT\SEG03-F-enhanced-2x.png
python scripts/minimax_video_cli.py enhance-tail --input OUT\SEG03-F-actual.png --output OUT\SEG03-F-enhanced-2x.png --scale 2
```

`extract-tail` 的 `--enhanced-output` 是可选的；已有尾帧只需要增强时，使用独立的 `enhance-tail`。增强输出适合作为下一段的上传候选或人工预览，不能被当成比原视频更有事实权重的新画面。

## 连续性与项目归档

- 真实生成视频的尾帧优先级高于分镜中的规划描述。下载后把生成视频、`*-F-actual.png` 和默认的 `*-F-enhanced-2x.png` 放进对应 `我的表述/02_分镜/素材/<场次段落>/`；下一段分镜把原始尾帧作为事实锚点，同时可把增强副本作为清晰度更好的上传候选。
- 增强副本只改变像素尺寸和边缘清晰度，不改变裁切、人物、脸、服装、道具、背景或原始竖屏构图。若增强后出现光晕、过锐边缘或任何疑似人物变化，回退到原始尾帧，不要继续叠加处理。
- 每一段生成前检查：是否保持 `multimodal_reference` 默认；唯一主空间锚点和最小参考集合是否成立；本段起始是参考上一段真实尾帧还是计划内剪切；末尾 1–2 秒是否稳定；是否存在自动换景、自动推拉或新对白。只有明确选择硬首尾帧时，再检查两端是否属于同一空间、主体数量和相近镜头家族。
- 如果要从上一段程序员中近景切到面部特写，不要让 API 自动插值；在稳定帧处标注计划内剪切，并分别生成或后期剪辑。
- 将 API 产物链接、任务状态和尾帧路径回填到当前 `EP/SC/SEG` 分镜文件与进度记录；不要改写 `原始剧本_全文.md`。

## 脚本与参考资料

- `scripts/minimax_video_cli.py`：预览、确认提交、轮询、下载、重命名、manifest、尾帧提取和非生成式增强。
- `references/api.md`：官方创建/查询接口、参数限制、首尾帧与多模态互斥规则、代理地址配置和尾帧增强边界。
