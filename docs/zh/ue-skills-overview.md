# UE 技能总览与安装

整理日期：2026-11-11。本套件包含 5 个直接服务于 Unreal 开发的技能，按引擎版本分为 `skills/ue5.8/` 与
`skills/ue5.9/` 两套；每套保留原名称和同级目录结构，便于共享脚本、相互引用和后续更新。
下文链接默认指向 5.8 稳定版。
这里说明用途与组合；实际执行规则以各技能 `SKILL.md` 和
[共享 UE 约定](../../skills/ue5.8/unreal-engine-mcp/references/shared-conventions.md) 为准。

## 五个技能怎么分工

| 技能 | 用途 | 典型任务 | 依赖 |
|---|---|---|---|
| [unreal-engine-mcp](unreal-engine-mcp.md) | 官方 MCP 连接、蓝图编程、开发查错 | 蓝图连线、动画蓝图、状态机、PCG、场景资产、日志与源码导航 | Python 标准库；编辑器操作需要 UE |
| [unreal-material-artist](unreal-material-artist.md) | 材质、Shader、贴图和参数契约 | 材质图、MI/MID/MPC、HLSL、Substrate、导入设置、成本审查 | 编辑器连接依赖 `unreal-engine-mcp`；图像工具需要 Pillow |
| [niagara-vfx-artist](niagara-vfx-artist.md) | 特效整体设计、系统制作与接入 | 爆炸、闪电、花瓣、烟火、拖尾、Bounds 与剔除 | 编辑器连接依赖 `unreal-engine-mcp`；Flipbook builder 依赖 `vfx-flipbook-generator` |
| [unreal-sequencer](unreal-sequencer.md) | 镜头、演出和序列检查 | 摄像机、切镜、骨骼动画轨、焦距与对焦、运行恢复 | 编辑器连接依赖 `unreal-engine-mcp`；图像证据检查需要 Pillow |
| [vfx-flipbook-generator](vfx-flipbook-generator.md) | 序列帧贴图制作与静态检查 | 视频抽帧、补帧计划、透明度检查、图集打包、SubUV 交接 | 本地处理需 Pillow；视频抽帧需 FFmpeg；UE 接入使用其他 UE 技能 |

PCG、动画蓝图和状态机已归入 `unreal-engine-mcp`，不需要另装同类桥接技能。
材质与 Niagara 负责不同资产层：Niagara 管系统、时序和 Renderer，材质技能管材质图及贴图。
这种分工可以由同一个助手依次完成，并不要求创建子代理。

## 按任务选择

| 目标 | 组合 |
|---|---|
| 二段跳、物理投掷物、计时爆炸、蓝图整理 | `unreal-engine-mcp`；有视觉效果时加材质和 Niagara |
| 动画蓝图、状态机、BlendSpace、Montage、AI 行为 | `unreal-engine-mcp`，逐项确认官方接口覆盖 |
| 花草树木、石块散布、PCG 参数与距离消失问题 | `unreal-engine-mcp`；叶片与风动材质加材质技能 |
| 漩涡、闪烁、溶解、水面、能量材质 | `unreal-material-artist` + `unreal-engine-mcp` |
| 闪电、爆炸、烟尘、花瓣、拖尾 | Niagara + 材质 + MCP；需要图集时加 Flipbook |
| 运镜、人物演出、近景与出片检查 | Sequencer + MCP；画面中的特效和材质按需加入 |
| MCP 失联、崩溃、错误日志、查找 C++ 实现 | `unreal-engine-mcp`；按问题资产增加对应专项技能 |

## 共用操作规则

1. 每个操作先发现当前编辑器的官方 MCP 工具及参数；只有确认缺口后，才对该操作使用 Epic Python Remote Execution 的公开 API。
2. 后台连接，不聚焦、缩放、移动或最小化窗口，不通过鼠标或控制台按键运行 Python。不自动打开时间线来绕过 API 限制。
3. 修改前核对目标 `.uproject`、资产和 PIE 状态。写入超时先回读，保护用户未保存内容，只保存本次目标包。
4. 新建或修改的模块添加中文说明、稳定可搜索 ID、入口与参数注释；保留既有运行时标识符及绑定。
5. 把静态结构、编译、编辑器采样、实际运行和视觉验收分开记录；未运行的案例不能记成通过。
6. 官方路由仍有缺口时报告具体边界，不安装自定义插件或 bridge 来补缺口。

## 版本目录与切换

| 目录 | 对应引擎 | 说明 |
|---|---|---|
| `skills/ue5.8/` | UE 5.8（审计于 5.8.4 / CL 58902052） | 稳定基线，首次安装默认使用 |
| `skills/ue5.9/` | UE 5.9（实测于 5.9.0 Preview / CL 60351404） | 只使用 5.9 原生工具与官方 MCP Python；正式版的工具名和参数可能变化，调用前以实时 schema 为准。使用前读 [5.9 审计](../../skills/ue5.9/unreal-engine-mcp/references/ue-5.9-preview-audit.md) 和 [工具覆盖与缺口](../../skills/ue5.9/unreal-engine-mcp/references/ue-5.9-tool-coverage.md) |

每套只对应自己的引擎版本：5.8 包只调用 5.8 的 MCP 工具，5.9 包只调用 5.9 的。
共享 client 会在发出任何请求前拒绝另一版本的编辑器，并提示应链接哪一套。

每个脚本和工具都带一个状态标签，各技能 `SKILL.md` 的工具表按此标注：

| 标签 | 含义 |
|---|---|
| `local` | 不需要编辑器：规划、图像检查、打包、清单、报告 |
| `5.8` / `5.9` | 连接编辑器，已在对应版本验证 |
| `untested` | 连接编辑器的版本无关路线，尚未在该构建上运行（仅 5.9 包） |
| `unported` | 仍按 5.8 工具名编写；在 5.9 编辑器上会在发出调用前被拒绝，改用该技能 `ue-5.9-*.md` 中的原生工具（仅 5.9 包） |

5.9 包中材质、Niagara 的编辑器 helper 和 Sequencer 的旧 builder / 采样 / 预览脚本目前都是
`unported`，迁移步骤见
[移植 helper](../../skills/ue5.9/unreal-engine-mcp/references/porting-helpers.md)。

两套技能名相同，`$unreal-engine-mcp` 等写法不变；同一时间只链接其中一套：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1 -UEVersion 5.9   # 切到 5.9
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1 -UEVersion 5.8   # 切回 5.8
```

不带 `-UEVersion` 时（包括 `update.ps1`）沿用当前已链接的版本，首次安装为 5.8。
切换后重启 Codex。五个包必须取自同一版本目录，不要混装。
原 `ue5.9-mcp` 开发分支已存档为 tag `archive/ue5.9-mcp`，5.8 快照基线为 `archive/ue5.8-baseline`。

## 安装压缩包

压缩包根目录包含 `skills/`、中文说明、各技能脚本与资源、安装脚本、依赖列表和校验清单。

### Windows

1. 解压到固定目录，例如 `D:\Tools\UE-Skills-2026-11-11`。
2. 在解压目录执行：

```powershell
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1
```

安装脚本把五个技能以目录联接注册到 `$CODEX_HOME/skills`，未设置时为
`$HOME/.codex/skills`；不会复制到 UE 工程、修改 `.uproject` 或启动编辑器。
已有同名联接会改指向解压目录；已有普通目录会拒绝覆盖。
若明确要替换普通目录，`-Replace` 会先移动为带时间戳的备份。
因此不要把解压目录放在临时文件夹，也不要在注册后删除它。

也可以先备份旧版，再手动把 `skills/ue5.8/`（或 `skills/ue5.9/`）内的五个目录复制到宿主的技能目录。
添加、删除或改名后重新启动 Codex，使技能清单刷新。
已经通过 AISkills 仓库联接安装的本机不需要为这次导出再安装一次。

### 其他系统

把同一版本目录（`skills/ue5.8/` 或 `skills/ue5.9/`）下的五个目录放在同一技能父目录下，
例如 `~/.codex/skills/`，保留目录名。
安装相应 `requirements.txt`；本包的 PowerShell 目录联接脚本面向 Windows。
目标 UE 编辑器的 MCP 是否可用，需要在该环境实际确认。

### 可选依赖

- 视频抽帧需要本机 FFmpeg，例如通过 `winget install Gyan.FFmpeg` 安装。
  本包不重复附送 FFmpeg 程序、第三方下载压缩包和本机缓存。
- 新图生成使用宿主的 `imagegen`，或另装并配置 `cm-imagegen`。
  它们属于可选创作能力；普通蓝图、已有材质、已有特效检查和本地帧图打包不依赖生成服务。
- `MCPBlueprintMetadata` 源码只保留在 5.8 包，仅用于明确要求的悬浮元数据扩展，默认不编译、不安装；5.9 包使用原生元数据工具，不附带该扩展。

## 连接与离线检查

目标 UE 需启用 Epic `ModelContextProtocol` 及任务需要的官方 Toolsets。
默认地址为 `http://127.0.0.1:8000/mcp`。启动方式和 Remote Execution 配置见
[内置 MCP](../../skills/ue5.8/unreal-engine-mcp/references/builtin-mcp.md) 与
[官方后台 Python](../../skills/ue5.8/unreal-engine-mcp/references/official-python-remote.md)。

在包根目录运行：

```powershell
python skills/ue5.8/unreal-engine-mcp/scripts/builtin_mcp.py --expect-project D:/Unreal/MyProject/MyProject.uproject status
python skills/ue5.8/unreal-engine-mcp/scripts/builtin_mcp.py list-toolsets
python skills/ue5.8/unreal-engine-mcp/scripts/run_offline_tests.py
```

把示例工程路径换成真实路径。`status` 不会启动或重启编辑器。
离线测试使用模拟数据与本地回环测试服务，不等于在 UE 中验收所有功能。

## 更新与交付边界

- 五个目录尽量作为同一版本整体更新，避免专项技能导入旧版共享客户端。
- 每套只面向自己的引擎版本；记录的能力和工具数是对应构建的实测结果，不是对后续版本的承诺。
- 文档规范（规则与验证记录分开、长文档带目录、80 列换行、description 写明何时使用等）写在各包的
  `unreal-engine-mcp/references/shared-conventions.md`，用 `python tools/ue_docs_lint.py` 检查，
  `--reflow` 可自动补目录并重排超宽段落。
- Sequencer 的部分后台兼容代码有严格引擎版本限制和 Epic 弃用风险；升级时先读当前源码与 schema，再执行相应验证。
- 图集就绪不等于特效已接入；预览 PNG 或逐帧视频不等于 MRQ/Movie Render Graph 正式出片。
- 本次打包只整理文档和现有技能文件，不连接或修改 UE 工程。检查结果见压缩包的 `CHECKS.zh-CN.md`，文件哈希见 `manifest.json`。
