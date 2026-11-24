# UE 5.9：Dataflow、渐变、数据类型与图验证

本页基于 5.9.0 Preview / CL 60351404 的独立候选资产实测。只操作测试资产，
没有保存关卡、打开图编辑器或运行 PIE。所有工具先取完整 live schema。
注册数与下面的代表验收分开；原始证据保存在忽略的 session 目录。

## Dataflow：两套合同同时存在

| Owner | 注册数 | 使用边界 |
|---|---:|---|
| `DataflowEditor.DataflowScriptingSubsystem` | 47 | 新的 graph/node/pin 字符串路径和类型化返回结构；含变量、子图、循环图、图绑定 |
| `DataflowAgent.DataflowAgentToolset` | 23 | 延续的 EdNode 引用和部分 JSON 字符串合同；5.8 技能已有基础 Dataflow 工作流 |

不能将两者参数混用，也不能把所有 Dataflow 能力称为 5.9 才有。
新路径从 `ListNodeTypes(dataflow=null, filter=...)` 开始；传 null 可只列注册类型。
`ListNodeTypes` 的描述不含完整 pins/properties，继续 `GetNodeTypeInfo(nodeType)`。
schema 中的示例 `FAddFloatsDataflowNode` 不保证已注册；本构建实际加法节点是
`FDataflowMathAddNode`，以发现结果为准。

实测流程：

1. `CreateDataflow(assetPath)` 返回资产引用；主图 `graphPath=""`。
2. `AddVariable` 用真实 `dataType="float"`，添加 2.5 与 1.5 两个默认值。
3. `AddNode` 使用 `Variable/<返回的变量名>` 建读取节点，并建立注册的加法节点。
   节点名使用稳定 ID；中文职责写入 comment。
4. `SetNodeProperties` 接受 **Unreal text export 字符串**，不是任意 JSON 值。
   实测设置 `bOverrideColor="True"` 与颜色结构体，回读 `bIsModified=true`。
   只修改已发现且非只读的属性；属性修改可能重建 pins，要重新获取引用。
5. `AddLink(outputPinPath,inputPinPath)` 后，通过 `GetGraphInfo` 回读精确双向
   pin links、节点类型与最终图连线。该工具可以替换输入连线或插入转换节点，
   不能只检查调用没有报错。
6. `AddComment` 写中文说明和稳定模块 ID；`GetDataflowInfo` 回读变量默认值，
   `GetGraphInfo` 回读 3 个计算/变量节点、1 个中文框和 2 条连线。按包保存并查 clean。

返回 `assetPath` 可以是 `/All/Game/...` 虚拟路径；不要将它当成本机文件。
NodePath 主图形如 `AuditAdd`，子图形如 `Module/Node`；PinPath 形如 `AuditAdd.A`，
不同于 UObject 的 `refPath`。使用工具返回的路径，不自行拼接生产对象引用。

本轮验证**结构写入、属性、类型/连线回读和保存**。没有执行图数值求值、
Cloth/Groom 解算或运行时接入。`ExecuteNodeFunction` 调用命名函数，不能据此
推断任意图都存在通用求值器。子图、ForEach、图绑定尚无本分支实测用例。

## CurveAtlas：渐变 RGB 与 alpha 分开

`EditorToolset.CurveAtlasToolset` 有 13 项注册工具。实测创建渐变和 64 像素
atlas、替换 RGB/alpha stops、采样和 atlas 行顺序，按包保存后均 clean。

- `CreateGradient` 默认不透明黑→白；`CreateAtlas` 默认空、textureSize 至少 2。
- `SetColorStops` 的 time 严格递增；`interpMode` 使用 live enum，如
  `RCIM_Linear`。color 中的 alpha **被忽略**，必须独立 `SetAlphaStops`。
- 实测红→蓝、alpha 0.2→0.8，`SampleGradient` 在 0 / 0.5 / 1 分别返回
  正确端点与 `(0.5,0,0.5,0.5)` 中点。采样会应用资产的色相/亮度等调整，
  因此生产资产的采样结果未必等于原始 key。
- `AddGradient` 后 `GetGradients` 的数组顺序就是行索引；不要添加重复成员。

Atlas 采样区间是 0–1。这个结果证明 CPU 渐变求值和资产成员关系；未验证材质
中实际纹理查找、渲染色彩或 Niagara runtime。CurveTable 在 5.8 已有，不能
把新的 CurveAtlas 封装与旧 CurveTable 当成同一组工具。

## 用户枚举与结构体

`UserDefinedEnumToolset` 8 项，`UserDefinedStructToolset` 14 项。
本构建采用原生封装；基础枚举/结构体概念不是新引擎功能。

枚举已验证 Create → 三项中文 AddEnumerator → MoveEnumerator → GetEnumerators。
返回字段 `name` 是稳定创作标识，`displayName` 是人类名称。**重排后 name 保持，
底层 integer value 随位置改变**；需要保留存档/外部协议整数语义时，不能随意重排。
测试枚举保存成功，不代表既有 Blueprint 或存档引用已回归。

结构体 Create 自带一个 bool 成员。`AddVariable(typeName,spec)` 的 typeName
仅接受 schema 的受支持集合；`spec.elementType` 为输出提示，写入时被忽略。
`ListVariables.elementType` 是**本地化显示文本**，本机返回“布尔”“浮点（单精度）”
“向量”，不能用它作为规范类型 ID 再传回 API。

实测添加 float 和 Vector，保留默认 bool，验证数值 2.5、Vector 默认值、中文
成员 tooltip、SaveGame 标志及结构体中文 tooltip。默认值是字符串编码，
读回可以规范化（Vector 例为 `1.000000,2.000000,3.000000`）；比较语义值，
不要仅比较原始文本。此 AddVariable 路径不等同于任意自定义 struct/object 类型
支持；数组、Set、Map 仍需各自用例。

## Deformer Graph：已有注册面，作者流程待补

`OptimusScripting.DeformerGraphScriptingSubsystem` 注册 62 项，包括图/变量/
资源/组件绑定、kernel HLSL 与执行域、pins/links、loop、函数和 Compile。
比较的 5.8 DeformerGraph 插件不含这个 OptimusScripting 子模块；这说明本接口
是新增自动化表面，不能说 Deformer Graph 本身从 5.9 才存在。

本轮 `ListDataTypes` 与 `ListComponentSources` 已返回真实类型/HLSL 对应及
SkeletalMesh、Groom 等组件来源与 Vertex/Triangle 等执行域。类型返回的
`bCanBeVariable` / `bCanBeResource` / `bCanBePin` 不同，不能仅凭 displayName
选型。例如当前 `FloatProperty` 不可作 variable，`DoubleProperty` 可以。
项目 `/Game` 搜索没有 deformer fixture，未创建图、写 kernel、编译或绑定角色。
本分支尚无经过编译和真实变形验证的作者 helper；这属于可调用但流程未覆盖。

## 验证器与编辑器信息

- `SequenceValidatorSubsystem` 两项已调用：`GetValidationRules` 返回 4 条真实
  中文规则，`ValidateSequence(sequence,ruleNames=[])` 对已有 Fade 候选返回空
  findings，资产 dirty 保持 false。空数组仅代表所选规则未发现问题，不能代替
  摄像机、事件、spawnable、播放或 MRQ 验收；规则名必须取自 live 返回。
- `UndoHistoryToolset.GetRecentTransactions` / `GetTransactionDetails` 已取得
  真实事务及修改对象；没有执行 Undo/Redo。其 accessMode 是 execute，说明
  工具名和注解都不能独立代替行为检查。
- `PluginToolset.GetPluginInfo` 返回安装/挂载元数据；不是插件能力的运行验收。
- `SourceControlHelpers.QueryProvider` 返回 Enabled=No、Connected=No。
  没有提交/checkout/revert/push；38 项源控注册接口不能算已连接仓库或已接入流程。

按需从 [覆盖与待补清单](ue-5.9-tool-coverage.md) 回到整体版本判断。
