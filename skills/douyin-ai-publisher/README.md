# 抖音 AI 发布助手：安装与使用

整理日期：2026-10-27。当前以经营账号、积累稳定粉丝为目标。视频由创作者提供；没有新视频时，可在明确要求下制作同栏目 AI 图文。具体商业请求以后再处理。

这是可放进 GitHub 的 Skill 源码包。一次具体发布指令可以覆盖素材分析、相关话题、包装、填写、最终提交和结果核验。“一键”依赖当前可用的浏览器工具、已登录账号和实际素材，不是独立运行的自动发帖程序。

## 从哪里开始

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | Codex 实际使用的工作指令 |
| [内容、热点与复盘](references/content-and-trends.md) | 观众价值、相关热点、视频/图文/口播、指标口径 |
| [发布执行](references/publishing.md) | 真实上传、AI声明、一次提交、状态核验与防重 |
| [合规与后续商业分支](references/compliance-and-monetization.md) | AI标识、真实性、权利及以后商业稿的适用要求 |
| [空白模板](assets/templates/) | 运营档案、四份表格、单条发布包结构 |
| [初始化工具](scripts/init_workspace.py) | 只创建缺失的本地运营档案与表头，不覆盖旧数据 |
| [发布账本工具](scripts/release_ledger.py) | 记录媒体/文案散列、一次授权和实际作品状态；不操作平台 |

## 在新电脑安装

先取得仓库源码，或打开已有克隆；已有工作未提交时先保留，不直接覆盖目录：

```powershell
git clone https://github.com/LuckyWDGS/AISkills.git
```

在 Codex 中发送：

```text
请使用 $skill-installer 从 https://github.com/LuckyWDGS/AISkills 的
skills/douyin-ai-publisher 安装抖音AI发布助手。
如果已有同名Skill，先比较本机修改并保留备份，再更新；不要安装两个同名副本。
```

也可按当前 Codex 的本地 Skill 目录复制整个 `douyin-ai-publisher` 文件夹。按[官方 OpenAI 文档](https://developers.openai.com/codex/skills)，当前推荐个人目录为 `~/.agents/skills/`，仓库内为 `.agents/skills/`。本项目历史机器已从 `~/.codex/skills/` 加载个人 Skill，可保留当前有效安装；不要仅为备份另装一份同名 Skill。仓库的 `skills/` 是版本化源码，克隆到这里不等于已自动发现。以当前环境展示的 Skill 清单为准；未出现时重新打开会话或重启 Codex。

仓库中包含的是工作流文件，不包含浏览器登录。实际发布需可用的 Chrome DevTools MCP、受支持的电脑操作工具或既有连接器，以及用户本人完成的登录/安全验证；不读取或搬运 cookie。AI 图片生成另需当前可用的图像 Skill/工具，不承诺克隆仓库即可生成。

两个本地脚本使用 Python 3.10+ 标准库，不需要抖音 API key、第三方抖音 SDK 或 PyYAML。PyYAML 仅在运行 Codex 的 `quick_validate.py` 时需要。

## 初始化本地运营档案

在本仓库根目录执行；其它工作区把 `--root` 换成其绝对路径：

```powershell
python -B -X utf8 ./skills/douyin-ai-publisher/scripts/init_workspace.py --root (Get-Location).Path
```

输出位置为 `<root>/.codex/session/douyin-publisher/`，包括 `operations.json` 与四份 CSV。重复执行保留所有已有文件，不创建假账本、假作品或授权。初始化只代表字段准备完成，需按现场事实补档案。AISkills 已忽略 `.codex/session/`；其它仓库先确认该本地目录被排除于 Git。项目自己的经营文档与真实账号记录另行保留，不属于本技能源码包。

准备单条素材时，把 `assets/templates/release.template.json` 和 `publish.template.md` 复制到本地新发布目录，补完并分别保存为 `release.json` 和 `publish.md`。模板中的 `null` 和待补内容不是已核事实；模板不可直接登记或发布。登记后的 `release.json` 保持原字节，实际结果写账本和 `publish.md`。

## 四种常用指令

只准备已有视频：

```text
$douyin-ai-publisher
分析我这次附上的视频，准备抖音标题、正文、封面和相关话题，核AI声明。
目标是吸引愿意持续看童话空间的粉丝。只准备发布包，暂不公开。
```

明确发布一个视频：

```text
$douyin-ai-publisher
把我这次附上的视频在当前核验的抖音账号公开、立即发布一次。
根据实际内容确定标题、正文、封面与强相关话题，开启AI生成声明。
本次授权完成填写和最终提交，仅抖音，不同步其它平台、不挂商品、不投流。
核对是否重复后执行，提交一次并报告真实作品链接与状态。
```

无视频，生成图文后发布：

```text
$douyin-ai-publisher
没有新视频。为现有童话空间栏目生成一组原创AI图片，保持同一美术方向，
每张给不同的空间细节，逐张验图后编排图文。
核当前相关话题，标明AI虚构创作，在当前核验账号公开、立即发布一条。
本次授权图片生成、填写与最终提交；不要生成视频或同步其它平台。
```

复盘一条已发作品：

```text
$douyin-ai-publisher
复盘我指定链接的已发作品，读取现在可见的播放、留存、收藏分享与作品吸粉数据。
注明观察时间、作品年龄和缺失字段，给出保留点和下一条最值得改的一项。
不要重发、评论、改主页或建立自动监控。
```

账号、素材或权利存在真实缺口时，只补该项；已明确的单条授权不反复询问。只问建议、整理资料或安装 Skill 不授权实际发帖。定时请求要明确日期、时间和时区，当前界面能力现场核验。

## 发布账本如何使用

账本脚本不是发布器。Codex 在浏览器中完成媒体和字段核验，再按[发布执行](references/publishing.md)记 `staged → authorized → submitting`，随后只点击一次最终提交，并记录实际 `under_review / scheduled / published`。

`register` 参数为 `--ledger --account --kind --media --package`；`transition` 参数为 `--ledger --release-id --state --evidence`，平台状态另带现场取得的 `--work-id` 或作品专属 `--work-url`。路径有空格时加引号；用 `python -B -X utf8 ... --help` 查看完整参数。由 Codex 绑定真实值，不把本说明的示例当执行证据。

同账号同顺序媒体按内容散列去重，改标题不绕过。`submitting` 或 `submission_unknown` 只核验已有作品，不再次提交。脚本不验证账号/权利/真实发布授权，也不能判断一个非空作品 ID 是真是假；`UI:` 证据必须来自本次实际界面。已发终态不回写；之后补到的公开链接或复盘结果可记 `publish.md`，不为补链接重发或修改已登记包。

## 换电脑与备份的边界

GitHub 保存 Skill、经营文档与空模板。账号后台、真实运营表、发布账本、原媒体和运行证据按项目现有安排保存，真实账号记录不放到公开包。

换电脑还需通过用户自己的私下文件迁移方式保留以下资料：

- `ledger.json`、`operations.json` 与真实 CSV，防止把“本地没有记录”误判成平台没发过。
- 每次发布目录中的原始 `release.json`、`publish.md`、作品身份与必要证据，以及对应原媒体或可靠持久副本。
- 未提交/提交未知/审核中作品的精确状态；迁移不把未知状态重置成可发布。无需搬运 ASR 虚拟环境、缓存模型或登录凭证。

旧账本包含旧绝对路径：已发历史即使原路径失效仍可读取，新路径同内容散列仍可去重。保留旧快照；未提交包换路径按本地未提交作废与重新登记规则办理，提交未知先只读查平台。**只克隆空模板，不能据此重发旧作品**。尚未迁移账本或无法核平台历史时，先完成本地准备，待历史核清再提交。

## 已核验到哪一步

| 项目 | 已有证据与限度 |
| --- | --- |
| 单条视频 | 2026-10-09完成真实上传、竖横封面、AI声明、一次公开即时提交；先审核中，后已发布；公开作品与播放已核 |
| 音轨 | 当条有本地可靠自动转写；不宣称全片主观听审或完整混音验收 |
| 图文与定时 | 流程已编写；本 Skill 尚无相应最终提交实测证据 |
| 本地账本 | 合成检查验证去重、未知不重提、媒体/包散列漂移阻断、作品身份及UI证据必填；这些不是平台实发测试 |
| 涨粉效果 | 没有在2026-10-27重查后台，不从一次发成功推导增长有效 |
| 热点与规则 | 原研究截至2026-10-09；每次实际发布另核相关热点和当前入口 |

2026-10-27这次工作只整理、验证本地工具并备份到 GitHub，不操作社交账号。后续更新以实际使用证据为准。
