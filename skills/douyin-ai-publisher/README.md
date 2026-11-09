# 抖音 AI 发布助手：安装与使用

整理日期：2026-11-08。

这是可放进 GitHub 的 Skill 源码包，适用于能操作浏览器的 Agent（Claude Code、Codex 等）。一次明确的指令可以覆盖：成片检查、相关话题、文案包装、平台填写、交接或一次提交、结果核验。它依赖当前可用的浏览器工具、用户已登录的账号和实际素材，不是独立运行的自动发帖程序。

默认行为：**填好发布页后停下，由用户审核并手动点“发布”**。只有用户对某一条作品明确说“这次由你点发布”，执行者才提交一次。

## 文件

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent 实际执行的工作指令和标准流程 |
| [成片检查](references/media-qa.md) | 画幅、分辨率、开头、遮挡区、响度等检查项和参考值 |
| [内容、热点与复盘](references/content-and-trends.md) | 观众承诺、热点来源与降级、话题选择、包装、指标口径 |
| [发布执行](references/publishing.md) | 数据位置、登录预检、上传、交接、一次提交、状态定义 |
| [界面笔记](references/ui-notes.md) | 带日期的平台界面观察：入口、上传限制、实测记录 |
| [合规与变现](references/compliance-and-monetization.md) | AI 标识、真实性、权利，以及以后商业稿的要求 |
| [模板](assets/templates/) | 运营档案、四份表格、发布包模板 |
| [scripts/](scripts/) | 见下方“脚本” |

## 安装

取得源码：

```powershell
git clone https://github.com/LuckyWDGS/AISkills.git
```

把整个 `skills/douyin-ai-publisher` 文件夹放到所用 Agent 的 Skill 目录：

| Agent | 个人目录 | 项目内目录 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.agents/skills/`（旧机器可能用 `~/.codex/skills/`） | `.agents/skills/` |

已有同名 Skill 时先比较本机修改并备份，再更新；不要装两份同名副本。装好后以 Agent 实际显示的 Skill 列表为准，没出现就重开会话。`agents/openai.yaml` 只是 Codex 的界面元数据，其他 Agent 可忽略。

仓库不包含浏览器登录。发布需要可用的浏览器工具，以及用户本人完成的登录和安全验证；脚本不读取或搬运 cookie。AI 生图另需当前可用的图像工具。

## 脚本

全部使用 Python 3.10+ 标准库，不需要抖音 API key 或第三方 SDK。`inspect_media.py` 另需 PATH 中有 `ffmpeg` 和 `ffprobe`。脚本都不上传、不发布。

| 脚本 | 作用 |
| --- | --- |
| `init_workspace.py --account <账号ID>` | 创建账号目录及缺失的运营档案和表格，不覆盖已有文件 |
| `inspect_media.py --out-dir <目录> <素材...>` | 成片检查：参数、hash、响度、黑场、静音；导出关键帧联系表、手机推荐流预览（标出遮挡区）、竖 3:4 和横 4:3 封面候选 |
| `prefill_release.py draft` | 从检查报告生成 `release.json` 草稿（带 `_draft` 标记，不能直接登记） |
| `prefill_release.py check` | 列出发布包登记前的缺项，包括未处理的检查警告 |
| `release_ledger.py register / transition / list / where` | 登记、记录状态、查重、显示账号目录 |

### 数据位置

运行数据按账号集中存放，跨项目共用一份账本查重：

```text
~/.douyin-publisher/<账号ID>/      可用环境变量 DOUYIN_PUBLISHER_HOME 改根目录
  operations.json  ledger.json  *.csv  releases/<日期-短名>/
```

```powershell
python -B -X utf8 ./skills/douyin-ai-publisher/scripts/init_workspace.py --account <账号ID>
python -B -X utf8 ./skills/douyin-ai-publisher/scripts/release_ledger.py where --account <账号ID>
```

旧版数据在 `<项目>/.codex/session/douyin-publisher/`，迁移方法见[发布执行 › 旧版项目内数据](references/publishing.md#旧版项目内数据)。迁移前仍可用 `--ledger <旧账本绝对路径>` 继续使用旧账本；`init_workspace.py --root <项目>` 保留为旧版用法。

### 一条视频的典型命令

```powershell
$S = "./skills/douyin-ai-publisher/scripts"
$R = "$HOME/.douyin-publisher/<账号ID>/releases/20261108-示例"
python -B -X utf8 $S/inspect_media.py --out-dir $R/qa <成片.mp4>
python -B -X utf8 $S/prefill_release.py draft --report $R/qa/media_report.json --account <账号ID> --out $R/release.json
# 补齐 release.json，删除 _draft
python -B -X utf8 $S/prefill_release.py check $R/release.json
python -B -X utf8 $S/release_ledger.py register --account <账号ID> --kind video --media <成片.mp4> --package $R/release.json
```

## 常用指令

只准备发布包：

```text
使用 douyin-ai-publisher：检查我附上的视频，准备抖音标题、正文、封面和相关话题，核对 AI 声明。
目标观众是 <你的栏目受众>。只准备发布包，暂不上传。
```

发布一条视频（默认停在发布页）：

```text
使用 douyin-ai-publisher：把我附上的视频发到当前抖音账号。
根据实际内容确定标题、正文、封面和强相关话题，开启 AI 生成声明，只发抖音，不挂商品、不投流。
填好后停在发布页，我审核后自己点发布。
```

授权执行者最终提交（仅本条）：

```text
……其余同上。这一条由你点击发布，公开、立即发布一次，然后核验作品状态和链接。
```

没有视频，生成图文：

```text
使用 douyin-ai-publisher：没有新视频。为 <你的栏目> 生成一组同一美术方向的原创 AI 图片，
每张展示不同细节，逐张验图后编排图文，标明 AI 创作。填好后停在发布页。
```

复盘一条作品：

```text
使用 douyin-ai-publisher：复盘 <作品链接>，读取现在可见的播放、留存、收藏分享和作品吸粉数据，
注明观察时间、作品年龄和缺失字段，给出保留点和下一条最值得改的一项。不要重发、评论或建立监控。
```

账号、素材或权利有真实缺口时，只问该项；已明确的单条授权不反复确认。只是问建议、整理资料或安装 Skill，不等于授权发帖。

## 账本的边界

账本脚本不是发布器。状态顺序为 `prepared → staged →（交接给用户）`，或在本条授权下 `staged → authorized → submitting → 平台结果`，详见[一次提交与结果状态](references/publishing.md#一次提交与结果状态)。

- 同账号、同顺序素材按内容 hash 查重；改标题不能绕过。
- 含 `_draft` 或 `_template` 的包拒绝登记。
- `submitting` / `submission_unknown` 只能只读核验，不能再次提交。
- 脚本不验证账号、权利或授权真伪，也不能判断作品 ID 真假；`UI:` 证据必须来自本次实际界面。

## 换电脑

GitHub 只保存 Skill 源码和空模板。需要用户自己私下迁移：

- 账号目录下的 `ledger.json`、`operations.json`、CSV 和 `releases/`，否则“本地没记录”会被误当成“平台没发过”。
- 发布包对应的原媒体或可靠副本。
- 未提交、提交未知、审核中作品的准确状态；迁移不能把未知状态重置成可发布。

**只克隆空模板，不能据此重发旧作品。**

## 已验证到哪一步

| 项目 | 证据与限度 |
| --- | --- |
| 单条视频 | 2026-10-09 完成真实上传、竖横封面、AI 声明、一次公开即时提交；先审核中，后已发布 |
| 图文与定时 | 流程已编写，尚无最终提交实测 |
| 成片检查脚本 | 2026-11-08 用 1280×720 横屏样片验证：正确报出横屏、720p、响度偏小，导出联系表、推荐流预览和封面候选 |
| 账本与预填 | 2026-11-08 本地验证：草稿拒绝登记、缺项检查、重复素材拦截、未授权不能进入 submitting、旧账本可读；这些不是平台实发测试 |
| 热点与规则 | 每次实际发布另核当次热点和当前入口 |
