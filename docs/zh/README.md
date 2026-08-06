# Skills 中文说明与快速选择

这里是仓库内 19 个 Skill 的用户入口。每个 Skill 都说明三件事：它解决
什么问题、什么时候值得用、以及可以直接复制的开始方式。文档只做解释，
真正的触发规则和安全边界仍以对应 `skills/<name>/SKILL.md` 为准。

## 怎么让 Codex 使用 Skill

通常直接用自然语言描述目标即可，Codex 会按任务选择技能。需要明确指定
时，在提示词中写 `$<skill-name>`，例如：

```text
$unreal-bridge 检查当前打开的 UE5.8 编辑器，列出可用 MCP 工具并确认 PIE 状态。
```

一次任务可以组合多个技能，但建议先指定一个主技能，再说明辅助目标。例如：

```text
$feature-experience 规划一个带加载、空态和错误态的搜索功能；如果需要落地界面，
再用 $ui-from-design 对照这张设计图实现。
```

## 快速判断

- 有明确设计图，要按图实现界面：`ui-from-design`。
- 只有功能想法，还没有完整流程：`feature-experience`。
- 普通生图、改图、UI mockup：`cm-imagegen`；要修 prompt、定风格或做内容策略：
  `image-generation-director`。
- 明确提到 Mentalout、Snow AI 或 `image.mentalout.top`：`mentalout-image-browser`。
- UE 编辑器、关卡、蓝图、资产自动化：`unreal-bridge`；材质/Shader：
  `unreal-material-artist`；Niagara：`niagara-vfx-artist`。
- 浏览器一次性操作：`playwright`；需要持续调试、刷新和视觉 QA：
  `playwright-interactive`。
- 桌面截图：`screenshot`；把上传图片保存到项目并可跨会话找回：`session-picture`。

## 技能总览

### 产品、工程与应用

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [feature-experience](./feature-experience.md) | 把功能点整理成完整模块、流程、状态、数据和验证方案 | 有功能想法，但入口、空态、错误态或真实数据关系还不清楚 | `$feature-experience 设计一个带缓存、重试和空态的收藏功能` |
| [chatgpt-apps](./chatgpt-apps.md) | 搭建和排查 ChatGPT Apps SDK、MCP server、Widget、工具注册和 CSP | 要做 ChatGPT App，或把现有 MCP/网页能力接进 ChatGPT | `$chatgpt-apps 搭一个带 Widget 的 MCP App，先查最新官方文档` |
| [codex-session-continuity](./codex-session-continuity.md) | 维护 `HANDOFF.md`、项目事实、决策、资产和验证记录 | 任务跨很多轮、需要换窗口，或准备暂停/交接项目 | `$codex-session-continuity 整理当前项目交接和下一步` |

### 图片、角色、视频与声音

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [cm-imagegen](./cm-imagegen.md) | 常规生图、图生图、改图、UI mockup、海报、产品图和批量素材 | 需要直接生成或编辑图片，且没有指定其他图片平台 | `$cm-imagegen 生成一张俯视角科幻竞技场地图概念图` |
| [image-generation-director](./image-generation-director.md) | 做创意方向、Prompt 修复、风格锁定、趋势选题和图片转视频规划 | 画面方向不稳定，或要把一个视觉想法扩展成内容/视频方案 | `$image-generation-director 保留这张图的服装和构图，重写成可用 prompt` |
| [fantasy-character-design](./fantasy-character-design.md) | 生成角色设定板、三视图、服装/法器细节和参考权重包 | 需要先锁定玄幻、仙侠、神女、女帝或其他主角形象 | `$fantasy-character-design 做一张仙侠女帝角色设定板和三视图` |
| [short-video-storyboard](./short-video-storyboard.md) | 把剧本拆成分镜、首尾帧、关键帧、图文镜头卡和视频 Prompt | 需要做 9 格/25 格分镜、连续短视频或国内模型提示词 | `$short-video-storyboard 把这段文案拆成 10 个连续镜头和首尾帧提示词` |
| [speech](./speech.md) | 通过 OpenAI Audio API 生成旁白、TTS、提示音和批量音频 | 有文字需要变成语音；需要本机 `OPENAI_API_KEY` | `$speech 把这段教程文案生成普通话旁白并保存为 wav` |
| [mentalout-image-browser](./mentalout-image-browser.md) | 驱动 Mentalout/Snow AI 网页完成图像生成或编辑 | 用户明确指定 `image.mentalout.top`、Mentalout 或 Snow AI | `$mentalout-image-browser 用这张参考图生成三张统一风格变体` |
| [session-picture](./session-picture.md) | 保存、标记、校验、查找和清理项目图片资产 | 上传了截图/参考图，且后续会话仍需要找回它 | `$session-picture 保存这张调试截图并登记到项目图片索引` |

### Unreal Engine 与实时内容

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [unreal-bridge](./unreal-bridge.md) | 通过 UE5.8 官方 MCP 操作编辑器、资产、关卡、蓝图、PIE 和日志 | 需要 Codex 直接检查或修改正在运行的 Unreal 编辑器 | `$unreal-bridge 检查 UE5.8 MCP，读取当前关卡并运行 20 秒 PIE 验证` |
| [unreal-material-artist](./unreal-material-artist.md) | 设计、审查和优化 UE 材质图、Shader、贴图、HLSL、Substrate 和预算 | 火焰、能量、UI、后处理、Decal、Niagara 材质或 Shader 性能问题 | `$unreal-material-artist 审查这个 Niagara 材质的透明度、采样数和发光预算` |
| [niagara-vfx-artist](./niagara-vfx-artist.md) | 设计、实现和优化 Niagara 发射器、渲染器、材质和 VFX 层级 | 火焰、命中、护盾、爆炸、拖尾、流体或移动端 VFX | `$niagara-vfx-artist 把这个能量护盾参考拆成可实现的 Niagara 分层方案` |
| [vfx-flipbook-generator](./vfx-flipbook-generator.md) | 生成、补帧、修复和打包烟尘、火焰、爆炸等 Flipbook/SubUV Atlas | 需要 Sprite Sheet、序列图、Power-of-two 图集或 Niagara SubUV 资源 | `$vfx-flipbook-generator 把 12 张火焰参考帧扩展成 64 格透明图集` |
| [pakskill](./pakskill.md) | 使用 UnrealPakTool 打包、检查、清理和安装 `.pak`/DLC | 要打包 Unreal 内容、校验输出或推送到 Android 设备 | `$pakskill 按现有配置打包 DLC，并校验设备上的 pak SHA1` |

### 浏览器、界面与测试

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [ui-from-design](./ui-from-design.md) | 把设计图、截图、Mockup 或原型转换成可实现界面 | 用户明确说“按这张图实现/匹配这个 UI” | `$ui-from-design 按这张设计图实现响应式设置页，并补齐空态和错误态` |
| [playwright](./playwright.md) | 用 CLI 驱动真实浏览器进行导航、点击、输入、截图和数据读取 | 一次性操作网页或本地 Web 应用，不需要持久调试会话 | `$playwright 打开本地站点，填写表单并截图提交成功状态` |
| [playwright-interactive](./playwright-interactive.md) | 保持浏览器/Electron 会话，反复刷新、交互和做功能/视觉 QA | 需要长时间调试 dev server、网页游戏或 Electron 应用 | `$playwright-interactive 对这个网页游戏做一轮功能和响应式视觉 QA` |
| [screenshot](./screenshot.md) | 截取桌面、窗口、应用或指定区域的系统截图 | 目标不是浏览器，或用户明确要求系统级截图 | `$screenshot 截取当前 Unreal 编辑器窗口并保存到指定路径` |

## 深入说明

- 上表中的链接对应每个 Skill 的中文说明页，适合先看用途和边界。
- 真正执行时优先阅读 `skills/<skill-name>/SKILL.md`；它包含工具、验证、
  安全和回退规则。
- 如果一个请求跨多个领域，先选主技能，再用一句话说明辅助目标，不要同时
  强行调用所有技能。
