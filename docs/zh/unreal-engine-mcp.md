# unreal-engine-mcp

`unreal-engine-mcp`（原 `unreal-bridge`）优先使用 UE 5.8+ 内置的 Epic MCP，面向蓝图程序开发、动画蓝图和状态机，以及编辑器资产操作。显示名称为 **Unreal Engine MCP**。

## 使用范围

- 读取蓝图事件、函数、变量、组件、引脚默认值和连接线，解释执行流程与数据来源。
- 编写或修改玩法蓝图，并在修改后读取验证、编译和检查实际行为。
- 检查动画蓝图、Pose 图、过渡规则、BlendSpace、Montage、Notify，以及 StateTree、行为树和 Control Rig；按具体操作确认官方支持范围。
- 为材质、Niagara 和 Flipbook 技能提供统一的官方 MCP 发现与连接方式。
- 沿着蓝图节点、父类、接口和参数写入链定位项目 C++、插件和对应版本的引擎源码。
- 区分 MCP 断连、编辑器忙碌、编译错误、运行错误和真正崩溃，保留日志、调用栈和复现证据后再修复。

## 持续操作约定

- 后台连接操作，不通过鼠标或键盘引导控制台执行 Python，不聚焦、缩小、最大化、移动或调整 UE 窗口。
- 优先 Epic MCP；缺少具体操作时，检查 UE 公开编辑器 API，可通过 Epic 自带 Python Remote Execution 后台执行；仍有缺口才使用少量自定义桥接。
- 新建或修改模块时添加中文注释框、固定可搜索模块 ID，以及入口、用途、关键参数、时序和条件说明。支持时填写中文分类和 Tooltip；保留原有标识符及绑定。标签是便于搜索的文字，不会因此增加运行时 Gameplay Tags。
- 先读取已有实现和用户未保存状态，再做局部修改。写入超时先回读，避免重复节点、重复绑定或重复执行。
- 验证按改动选择：注释核对文字、成员及拓扑；行为变化检查编译和相关运行结果。保护已有 PIE/调试会话，只保存目标包。

## 开发与查错参考

| 需要完成的任务 | 已整理的方法 |
|---|---|
| 实现、重构或交付模块 | [开发流程](../../skills/unreal-engine-mcp/references/developer-workflow.md)：定位入口和依赖、局部修改、超时回读、模块索引、按改动验证 |
| 查找代码或定位故障 | [诊断与源码导航](../../skills/unreal-engine-mcp/references/debugging-and-source-navigation.md)：蓝图到 C++ 的身份映射、数据/生命周期检查、崩溃证据与修复验证 |
| 不操作窗口地补齐 MCP 缺口 | [官方后台 Python](../../skills/unreal-engine-mcp/references/official-python-remote.md)：识别目标项目、使用引擎自带客户端、回读验证 |

这些是开发工作方法与能力边界，不会凭文档增加 UE 的 MCP 工具。断点单步、执行过的引脚、专用状态机编辑等能力仍要检查当前官方接口；静态连线不能冒充运行轨迹。

## 调用方式

```text
$unreal-engine-mcp 读取 BP_FirstPersonCharacter，解释事件和函数逻辑，导出执行线与数据线，并检查连接端点是否双向一致。
```

在技能目录下检查连接与工具：

```powershell
python scripts/builtin_mcp.py status
python scripts/builtin_mcp.py list-toolsets
python scripts/builtin_mcp.py describe-toolset BlueprintTools --brief
python scripts/builtin_mcp.py describe-tool BlueprintTools <工具名>
python scripts/builtin_mcp.py --expect-project <项目名> call <工具名> --toolset <toolset> --args-file <参数.json>
python scripts/builtin_mcp.py batch <步骤.jsonl> --dry-run   # 先校验，再去掉 --dry-run 执行
```

脚本需要 Python 3.10 及以上（仅用标准库）。`scripts/live_smoke.py` 只读地端到端检查全部工具；升级引擎后用 `scripts/record_fixtures.py --check` 检查契约测试样例是否仍然一致。

命令行会在两次运行之间保留 MCP 会话，重复调用约 0.3 秒（新会话约 2 秒），`--new-session` 可关闭。读多个数据用 `run-script`（编辑器内一次执行，任一步失败则整批失败）；写操作或需要逐步确认的步骤用 `batch`（逐步执行、遇错即停、可读回校验）。

只读导出某个蓝图（将路径替换为目标资产）：

```powershell
python scripts/inspect_blueprint.py /Game/Blueprints/BP_Player --out <项目运行输出目录> --verify-snapshot
```

输出原始读取记录、图快照、JSON/CSV 连接表和 Markdown 报告。脚本核对输入端与输出端的连接，不编译、不保存、不写图，也不调用可能使资产变脏的节点目录查询。输出目录必须为空或尚不存在。

## 官方优先与已知边界

每次从正在运行的 UE 获取工具清单和参数，按 **Epic MCP → 官方 Python Remote Execution（公开 `unreal.*` API）** 两级路由，第二级只用于 MCP 已证实未覆盖的单个操作。UnrealBridge 自定义插件及其 TCP 连接已停用，不再安装、启动或作为后备；也不修改引擎实现来绕过限制。

```powershell
python scripts/python_remote.py nodes
python scripts/python_remote.py --project <项目名> exec --file <会话目录>/probe.py
```

`python_remote.py` 从所选引擎加载 Epic 自带的 `remote_execution.py`，仅在恰好一个编辑器匹配 `--project` 时才执行，全程后台运行，不操作编辑器窗口。目标项目需在 Project Settings › Plugins › Python 中开启 Remote Execution（绑定 127.0.0.1，TTL 0）。

UE 5.8.4 的中文编辑器中，DSL 导出可能对非空图返回空字符串；应改用官方节点/引脚接口。执行引脚类型可能是 `执行`。动画状态机容器的节点枚举存在类型覆盖缺口，空结果不能证明状态机为空。`get_node_infos` 可以获取逻辑连接端点，不返回编辑器连线的像素曲线。

详细方法见技能中的 `references/blueprint-graph-inspection.md`、`references/animation-state-machines-mcp.md` 和 `references/ue-5.8.4-audit.md`。版本和工具数量是实测快照，后续更新以实时发现结果为准。
