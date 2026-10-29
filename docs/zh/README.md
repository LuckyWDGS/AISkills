# Skills 中文说明与快速选择

这里是仓库内 16 个 Skill 包的用户入口。每个 Skill 都说明三件事：它解决
什么问题、什么时候值得用、以及可以直接复制的开始方式。文档只做解释，
真正的触发规则和安全边界仍以对应 `skills/<name>/SKILL.md` 为准。

## 怎么让 Codex 使用 Skill

通常直接用自然语言描述目标即可，Codex 会按任务选择技能。需要明确指定
时，在提示词中写 `$<skill-name>`，例如：

```text
$unreal-engine-mcp 检查当前打开的 UE5.8 编辑器，列出可用 MCP 工具并确认 PIE 状态。
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
- UE 编辑器、关卡、蓝图、资产自动化：`unreal-engine-mcp`；材质/Shader：
  `unreal-material-artist`；Niagara：`niagara-vfx-artist`。
- 抖音 AI 内容包装、发布和复盘：`douyin-ai-publisher`；人像服装配方库需点名 `portrait-recipe-studio`。
- 自有 VPS 代理节点、订阅与分流排障：`vps-proxy-deploy`。

## 技能总览

### 产品、工程与应用

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [feature-experience](./feature-experience.md) | 把功能点整理成完整模块、流程、状态、数据和验证方案 | 有功能想法，但入口、空态、错误态或真实数据关系还不清楚 | `$feature-experience 设计一个带缓存、重试和空态的收藏功能` |
| [chatgpt-apps](./chatgpt-apps.md) | 搭建和排查 ChatGPT Apps SDK、MCP server、Widget、工具注册和 CSP | 要做 ChatGPT App，或把现有 MCP/网页能力接进 ChatGPT | `$chatgpt-apps 搭一个带 Widget 的 MCP App，先查最新官方文档` |
| [vps-proxy-deploy](./vps-proxy-deploy.md) | 部署、维护自有 VPS 代理节点及 Clash/Mihomo 订阅 | 自用节点、HTTPS 订阅、DNS、分流或性能需要排查 | `$vps-proxy-deploy 只读检查我现有节点和订阅，定位连接失败原因` |

### 图片、角色与视频

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [cm-imagegen](./cm-imagegen.md) | 常规生图、图生图、改图、UI mockup、海报、产品图和批量素材 | 需要直接生成或编辑图片，且没有指定其他图片平台 | `$cm-imagegen 生成一张俯视角科幻竞技场地图概念图` |
| [image-generation-director](./image-generation-director.md) | 做创意方向、Prompt 修复、风格锁定、趋势选题和图片转视频规划 | 画面方向不稳定，或要把一个视觉想法扩展成内容/视频方案 | `$image-generation-director 保留这张图的服装和构图，重写成可用 prompt` |
| [ai-video-prompt-director](./ai-video-prompt-director.md) | 将已确定的导演包编译成可复制视频提示词，按需适配 H3/Seedance | 已有剧情、镜头与参考，需要核对空间、动作、对白和声音 | `$ai-video-prompt-director 按已确定的导演包整理 Seedance 提示词` |
| [xiaohongshu-content-publisher](./xiaohongshu-content-publisher.md) | 小红书图文/视频包装、上传、授权发布与历史归档 | 需要准备一条笔记或整理已有发布记录 | `$xiaohongshu-content-publisher 整理这条笔记的素材和文案，先保存草稿` |
| [douyin-ai-publisher](./douyin-ai-publisher.md) | 分析素材、准备文案/封面/话题、执行授权发布并复盘 | 要发布或准备抖音 AI 视频、图文和口播内容 | `$douyin-ai-publisher 分析这个视频并准备标题、封面和相关话题，暂不发布` |
| [portrait-recipe-studio](./portrait-recipe-studio.md) | 人像与服装配方、参考审查和面容设计 | 明确需要使用这套提示词库；仅点名调用 | `$portrait-recipe-studio 根据参考选择合适的人像服装配方，先整理提示词` |
| [fantasy-character-design](./fantasy-character-design.md) | 生成角色设定板、三视图、服装/法器细节和参考权重包 | 需要先锁定玄幻、仙侠、神女、女帝或其他主角形象 | `$fantasy-character-design 做一张仙侠女帝角色设定板和三视图` |
| [short-video-storyboard](./short-video-storyboard.md) | 把剧本拆成分镜、首尾帧、关键帧、图文镜头卡和视频 Prompt | 需要做 9 格/25 格分镜、连续短视频或国内模型提示词 | `$short-video-storyboard 把这段文案拆成 10 个连续镜头和首尾帧提示词` |

### Unreal Engine 与实时内容

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [unreal-engine-mcp](./unreal-engine-mcp.md) | 通过 UE5.8 官方 MCP 操作编辑器、资产、关卡、蓝图、PIE 和日志 | 需要 Codex 直接检查或修改正在运行的 Unreal 编辑器 | `$unreal-engine-mcp 检查 UE5.8 MCP，读取当前关卡并运行 20 秒 PIE 验证` |
| [unreal-material-artist](./unreal-material-artist.md) | 设计、审查和优化 UE 材质图、Shader、贴图、HLSL、Substrate 和预算 | 火焰、能量、UI、后处理、Decal、Niagara 材质或 Shader 性能问题 | `$unreal-material-artist 审查这个 Niagara 材质的透明度、采样数和发光预算` |
| [niagara-vfx-artist](./niagara-vfx-artist.md) | 设计、实现和优化 Niagara 发射器、渲染器、材质和 VFX 层级 | 火焰、命中、护盾、爆炸、拖尾、流体或移动端 VFX | `$niagara-vfx-artist 把这个能量护盾参考拆成可实现的 Niagara 分层方案` |
| [vfx-flipbook-generator](./vfx-flipbook-generator.md) | 生成、补帧、修复和打包烟尘、火焰、爆炸等 Flipbook/SubUV Atlas | 需要 Sprite Sheet、序列图、Power-of-two 图集或 Niagara SubUV 资源 | `$vfx-flipbook-generator 把 12 张火焰参考帧扩展成 64 格透明图集` |

### 界面实现

| Skill | 它是干什么的 | 什么时候用 | 开始示例 |
|---|---|---|---|
| [ui-from-design](./ui-from-design.md) | 把设计图、截图、Mockup 或原型转换成可实现界面 | 用户明确说“按这张图实现/匹配这个 UI” | `$ui-from-design 按这张设计图实现响应式设置页，并补齐空态和错误态` |

## 深入说明

- 上表中的链接对应每个 Skill 的中文说明页，适合先看用途和边界。
- 真正执行时优先阅读 `skills/<skill-name>/SKILL.md`；它包含工具、验证、
  安全和回退规则。
- 如果一个请求跨多个领域，先选主技能，再用一句话说明辅助目标，不要同时
  强行调用所有技能。
