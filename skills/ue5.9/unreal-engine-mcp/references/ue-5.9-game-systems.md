# UE 5.9：游戏系统制作与验收

用于自动化测试、GAS、数据、网格碰撞，以及存档/设置/本地化任务。先读
[版本审计](ue-5.9-preview-audit.md)；完整玩法串联见 [game-production](game-production.md)。
本页依据 2026-11-15 目标编辑器的 full schema，以及 2026-11-16 的存档/设置实测，
不是与 5.8 的新增 API 差分。本轮已取得普通存档/设置的 PIE 读回与关卡旅行、
11 项 Native Automation、新封装的 12 组真实磁盘/API 验证，以及同一最终独立包
的跨进程保存/读回与正常退出。其余制作链按各段证据分别验收。
每次执行仍须 fresh identity、目标绝对工程路径与当前 schema；机器证据放 ignored session。

## Automation：选择自己的测试并取得完整结果

Owner 为 `AutomationTestToolset.AutomationTestToolset`，共 7 工具。它管理与 Session
Frontend 相同的 automation controller/worker；发现和运行都可能异步，须等真正完成。

1. 先确认运行归属；`DiscoverTests()` 初始化 worker 和测试列表，完成后才可调用其余工具。
   它标为 write，不能包装成无状态读取；重载 Python 测试后才按需
   `DiscoverTests(bForceRediscover=true)` 绕过缓存，不为轮询反复重发现。
2. `GetTestStatus()` 查 `Ready/Running/Disabled`。已有非本任务的运行时，不启动或取消测试。
3. `ListTests(nameFilter, tagFilter, limit)` 两个 filter 都是子串；对比 `total/returned`，
   默认 limit=200 可能截断。缩小范围，或在确有需要时 limit=0，再审阅目标案例的源码与副作用。
4. 精确运行优先 `RunTests(testNames=[完整路径])`，完整路径来自 ListTests。
   `RunTestsByFilter(filterExpression)` 适合已核对范围的批量：`StartsWith:System.Engine`、
   `^Foo`、`Bar$`、裸子串或 `Group:Smoke`，多个表达式用 `+` 连接；Group 来自 ini 配置。
   不把裸子串当精确名称，不直接发起未经范围审查的全套测试。
5. 有界等待异步结果，结合 `GetTestStatus()` 与 `GetTestResults()`。结果是当前或最近一次
   运行，不能仅凭旧 passed 数宣称本次通过；记录本次选择、每项 name/state、耗时、errors/warnings
   与 passed/failed/skipped/total。`NotRun/InProcess/Skipped` 不算通过，Success 仍可能有警告。
6. 仅在需要取消自己发起的运行时 `StopTests()`；它停止所有当前测试，没有每次运行的隔离 ID。
   true 只表示停止请求已发出；待定 RunTests 会以错误完成，还需查状态、结果和 fixture 清理。

验收遵循 [Automation.Scope](runtime-acceptance.md)：比较测试前后的 Actor、PIE、选择、页签和
dirty；不靠 Save All 或清 dirty 隐藏副作用。工具单测、资产编译、玩法 runtime 分别计数。

本构建原生 automation 测试的 flags 是强类型 `EAutomationTestFlags`，组合 mask
为全局常量 `EAutomationTestFlags_ApplicationContextMask`，不是枚举成员：

```cpp
constexpr EAutomationTestFlags Flags =
    EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter;
```

本轮 StarHopRuntime 首次 BuildPlugin 使用旧式 `constexpr uint32` 与
`EAutomationTestFlags::ApplicationContextMask`，实际报 C2838/C2065（mask 不是枚举成员）
及 C2678/C2440（测试宏不能用 uint32 完成强类型运算/返回）。安装头文件
`Misc/AutomationTest.h` 声明 `enum class`、`ENUM_CLASS_FLAGS` 和上述全局 mask。
改成所示写法后，第二次 BuildPlugin 完成并返回 ExitCode=0；随后目标编辑器发现并
执行了下文 11 项测试。flags 允许的运行上下文不是已经测试过的上下文，也不能据此
推导 UE 5.8 编译兼容。纯 codec 通过仍不能替代文件 I/O、真实对象反序列化或重启。

## GAS：能力作者、属性发现与真实 ASC 观测分开

`GASToolsets.GameplayAbilityToolset` 的专用作者只有 `CreateGameplayAbility`：
在明确制作任务授权下，传 `folderPath/assetName/parentClass` 创建候选 Ability Blueprint。
它通过专用 factory 创建 `Gameplay Ability Graph`，不能把普通 GameplayAbility 子类蓝图
的默认 EventGraph 等同于该合同；后续图逻辑仍走当前 Blueprint 作者工具并单独编译。

`GASToolsets.AttributeSetToolset` 提供 `FindAttributeSetClasses()`、
`ListAttributes(className)`，发现原生/蓝图 AttributeSet 和属性；这两项不创建或修改类。
`GASToolsets.AbilitySystemInspectorToolset` 则对实际持有 ASC 的 Actor 引用提供 4 项读取：

| 观测 | 用途与边界 |
|---|---|
| `GetGrantedAbilities(actor)` | 能力名、level、bIsActive；不代替实际输入激活或授予能力 |
| `GetAttributeValues(actor)` | fullName/setClassName、baseValue/currentValue；同名属性按完整名区分 |
| `GetActiveTags(actor)` | 当前拥有的标签，包含 loose 与 effect-granted；不单凭名称推断来源或计数 |
| `GetActiveEffects(actor)` | effectName、stackCount、总/剩余时长、grantedTags；-1 时长代表无限 |

先定位自己 PIE 的真正 ASC/Owner/Avatar 与 AttributeSet，再对激活、费用/冷却、效果叠层、
取消/重激活和结束清理采样；不要查询编辑器模板来证明角色运行正常。上述读取不提供能力授予、
GameplayEffect 作者或激活 API；需要时发现正式 Blueprint/C++ 路线。按
[GAS.ASC.Lifecycle](runtime-acceptance.md) 做运行验收，服务器权威/客户端复制另测。

### Cue 与 Gameplay Tags

`GASToolsets.GameplayCueToolset` 先用 ListCues/GetCueInfo/FindCueTagsWithoutNotifies
检查映射；GetCueInfo 只认项目 cue notify paths 内、恰好属于该 tag 的 notify。
缺少自己的 notify 不直接证明整个效果无法触发。创建时先确保 `GameplayCue.*` tag 存在，
再 `CreateCueNotifyAsset`；packagePath 必须属于项目 notify paths，bIsActor 决定 Actor/Static。

`ExecuteCueOnSelectedActor(cueTag, normalizedMagnitude, location, normal)` 依赖当前编辑器选择；
先记录选择并核实目标，结束恢复。可见结果需要 PIE 或已配置的 GameplayCueManager。
该调用明确 non-replicated；返回 true 只证明 dispatch，需实际观察效果/结束清理，不能证明联网复制。

`GameplayTagsToolset.GameplayTagsToolset` 可管理 11 项标签/来源能力。修改前用 GetTagInfo、
ListTagSources/ListTagSourceRoots、FindReferencersByTag 查来源、允许目录与影响资产。
AddTag 的 `tagSource` 是来源名，不是目录；优先显式指定可写 INI source。
空值受项目 EmptySourcePolicy 控制，可能回退默认来源或拒绝；Native/DataTable 来源不能当
普通 INI 写入。Rename/Remove/Move 后检查引用、配置 diff 与实际 runtime tag，不能只看列表更新。

## 数据：作者与 Registry 缓存查询分工

`EditorToolset.DataTableToolset`：SearchRowStructs → Create/ImportFile → GetSchema →
AddRows/SetRows → GetRows/ListRows；调用前核对各方法的当前 schema，别把示意链当统一参数接口。
SetRows 的 `values` 是 JSON 字符串，按 row/property 局部更新；GetSchema/GetRows 也返回 JSON 字符串。
导入列名必须匹配 struct；替换现有表要求同一 schema，默认 bReplaceExisting/bSave 都为 false。
行名改动需单独检查使用方；创建、读回、scoped save/reload 与玩法实际取值分层验收。
`EditorToolset.DataAssetToolset` 只有 Create/Diff；Create 要真实 `assetType` class 引用，
字段编辑需另发现对象属性合同，不能由 Create 推断任意数据对象已配置完成。

`DataRegistryToolset.DataRegistryTools` 的 7 项均为查询：ListRegistries → GetRegistryInfo/
GetSchema → ListDataSources/ListRuntimeSources → ListItems/GetItems。
ListDataSources 是编辑器定义来源；ListRuntimeSources 包含元来源展开的 transient 子来源，
比较其 availability、bIsInitialized、bIsTransient 与父来源。GetRegistryInfo 的 availability
是所有来源的最低可用性，DoesNotExist 也可能表示未初始化，不要直接判定资产丢失。
`GetItems(registryName, itemNames)` 仅返回已缓存数据；未缓存名字被省略，不自动 acquire/load，
ListItems 有名字不证明 GetItems 已可读。需要加载或持久化时另走正式 runtime/数据作者路线。

## 骨骼网格与 PhysicsAsset：从附件到受控模拟

`EditorToolset.SkeletalMeshToolset` 先读 Skeleton、BoneNames/Parent、Sockets、PhysicsAsset
和材质 slots；确认骨架兼容与共享引用后才修改候选。附件用
`AddSocket(mesh, socketName, boneName)`，随后 GetSocketBone/GetSocketTransform 读回。
`SetSocketTransform(mesh, socketName, translation, rotation, scale)` 可修改局部变换；
只传本次要改的分量，未提供的分量保持当前值。RenameSocket/RemoveSocket 前检查挂接使用方。
socket transform 是骨骼局部空间；GetBounds 是 reference pose，不包含动画变形。
验收至少覆盖 socket 名/父骨/局部变换、save/reload，以及实际动画中附件的世界姿态和缩放。

`PhysicsToolsets.PhysicsAssetToolset` 先 GetBodyNames/GetBodyShapes/GetConstraints，读回 physics
mode 与 mass scale。CreateFromMesh 会在网格同目录生成 `_PhysicsAsset`，bAssignToMesh 可改变
网格引用；先规划候选路径/碰名，不因自动生成成功就认定可用。兼容后用网格的 AssignPhysicsAsset。
缺 body 先 AddBody，再 SetSphere/SetCapsule/SetBox；同名 shape 会被替换，不会追加独立副本。
形状中心在骨骼局部空间；SetBox 的 extentX/Y/Z 是完整尺寸厘米，不能按半尺寸直接套用。
约束两端 body 必须存在；Bone1 是子、Bone2 是父，SetConstraintLimits 针对已存在约束，
显式核对 Free/Limited/Locked 与角度，不用默认值覆盖未计划的轴。
读回形状、mode、mass 和约束后保存重载，再测布娃娃/命中、稳定性、穿透、恢复与销毁清理；
结构读回不等于模拟通过，动画驱动、碰撞 profile 和 PhysicsAsset 也不能互相代验。

## StaticMesh：碰撞与 LOD 的不同验收

`EditorToolset.StaticMeshToolset` 先记录 LOD 数、三角形/顶点、thresholds、quality MinLOD、
collision complexity、Nanite 和材质。GenerateConvexCollisions 会替换已有 collision，
先在候选网格上执行并检查几何；collision complexity 回读不能证明 hull 形状正确。
静态查询、移动/阻挡、overlap 与需要的物理模拟分别测，别用复杂碰撞查询替代动态模拟验收。
`GenerateLods(trianglePercents)` 每项生成一个额外 LOD，比例相对 LOD0 且须大于 0、不超过 1。
`SetLodThresholds` 数量必须恰好等于 LOD 数，严格降序；screen-size 大于 1 也是合法值。
quality MinLOD setter 仅合并已列出的覆盖，保留未列出的质量档；-1 清除对应覆盖，fallback default 单独设置。
切换 Nanite 触发重建；IsNaniteMesh 可能短暂滞后，等完成再读，不把设置位当目标平台收益。
保存重载后测实际距离/质量档切换、轮廓与材质，再做目标平台 cook/runtime 和成本采样。

## 存档、用户设置、重映射与本地化

SaveGame 的版本迁移、槽位、缺失/损坏默认值及异步回调放在普通 Blueprint/C++ 运行模块；
写完需真实 save → load，并跨进程重启核验。本构建未发现可替代这些业务模块的专用 MCP owner。
2026-11-16 的普通 SaveGame 用例读回了保存成功、关卡旅行后的检查点/金币 ID 与设置，
且已收集金币没有重生；检查点由 fixture 移动角色触发，不能算完整玩家路线或跨进程验收。

### 损坏保护必须在原生反序列化之前

此次把隔离 QA 槽替换为普通损坏字节后，直接 `LoadGameFromSlot` 进入原生反序列化，
触发 `UnrealNames` assertion 并使编辑器退出。`IsValid`、CastFailed 或返回值判断都在
调用之后，无法拦截这类崩溃；不要把任意坏字节反复送入正在使用的编辑器。

需要防损坏时，可在**项目 Runtime 插件**内提供 BlueprintCallable 存档库，以正式
`SaveGameToMemory` / `SaveDataToSlot` / `LoadDataFromSlot` / `LoadGameFromMemory`
完成序列化和 I/O。这是随游戏构建的业务逻辑，不是 MCP bridge；不增加远程控制端点，
不修改引擎，也不把项目插件的函数冒充 Epic 内置工具。重载后仍需发现其实际 Blueprint schema。

- 在调用 `LoadGameFromMemory` 前检查封装 magic、封装/业务版本、固定头长度、声明总长、
  项目类白名单及 header/body CRC。先做溢出安全的长度运算和大小上限检查，再切片、分配。
  Windows generic slot 可在读取前检查文件大小；其他平台是否能预检须按实际 save system 确认。
  本构建写出的 GVAS version 为 3，不能仅凭外层版本假定任意引擎 payload 都可读。
- CRC 用于意外损坏检测，不是认证或完整 GVAS 结构校验；校验有效但故意构造的畸形 payload
  仍可能伤及原生读取器。只验 GVAS 前缀的 codec 不可宣称能安全反序列化任意输入。
  读出后还要核对真实类、实际业务版本及字段值域；版本不一致不得接纳为当前数据。
- Load 应自行检查主档与备份，不要用外层 `DoesSaveGameExist(primary)` 跳过“主档丢失、
  备份仍在”的恢复。区分 Missing、Loaded、RecoveredBackup、Invalid 与 Unsupported；
  双方均 Missing 可创建新档，Invalid/Unsupported 不能当作 Missing。
  明确识别的未来封装/业务版本不能降级回旧备份后再覆盖。恢复只读，不自动改写源文件。
- 轮换备份前确认旧主档确实能加载；**CRC 有效不等于可恢复**。主档封装有效但真实类型/
  版本核验失败时，不能把它覆盖到刚恢复的有效备份。保留可信旧档，必要的备份写入失败则停止。
  有旧文件却主档与备份都不可读时保持写保护；未来格式也应在 Save 入口拒绝，而不只依赖蓝图布尔位。
- 用真实写入返回值和回读一致性判定成功。内存快照、磁盘可恢复检查点、最近保存结果分别记录；
  保存失败不能显示“已保存”，也不能因为内存已设 `bHasCheckpoint` 就启用会重新读盘的 Load。
  失败保留原数据并显示状态；已有可恢复检查点不应仅因一次设置写入失败而丢失其身份。

验证分为 codec、真实槽 I/O、原生对象读回、关卡旅行和独立进程。隔离槽覆盖缺失、截断/CRC
破损、备份恢复、双方破损、未来版本、主档仅封装有效但不可加载、真实写失败；再以相同
用户数据目录启动第二个进程读取。fixture 字节往返不算对象反序列化通过，PIE 旅行不算重启。

### 本轮存档验证结果

2026-11-16，在 UE 5.9 Preview / CL 60351404 目标编辑器运行
`StarHop.Save.Codec.*` 9 项和 `StarHop.Save.Policy.*` 2 项 Native Automation，
全部为 Success：passed=11、failed=0、skipped=0，各项 errors/warnings 均为空。
其中 codec 覆盖字节往返、截断、头/CRC、声明长度、大小上限、未知版本与非法槽名；
policy 覆盖 16 种主档/备份状态组合，以及实际可加载性对备份轮换资格的影响。
这些是纯内存 codec/策略测试，不调用真实槽或原生 SaveGame 反序列化。

随后独立磁盘 runner 通过 12 组案例；每组使用全新 `StarHop_DiskQA_*` 槽，
通过正式插件 API 保存/加载真实 SG_StarHop 对象，并比较全部业务字段及文件字节：

| 组数 | 真实磁盘/API 场景与结果 |
|---|---|
| 2 | 缺失主/备份返回 Missing 且不落盘；两次保存/加载字段一致，第二次备份等于旧主档 |
| 2 | CRC 破损主档、有备份但缺失主档：均只读恢复备份；之后重建主档仍保留有效备份 |
| 2 | 双方无效、主档无效且无备份：加载 Invalid、保存 false，原有哈希不变 |
| 3 | 未来封装、未来业务版本、当前主档配未来备份：保存均拒绝且哈希不变；未来主档不回退，当前主档仍可读取 |
| 1 | 仅将已验证 payload 的外层业务版本改为 0：实际 schema=1 导致一致性拒绝，恢复并保留好备份后成功重建主档 |
| 2 | 精确 QA 主档或备份设置 Windows 只读属性：真实写入返回 false；主档受保护时先保留旧档备份，备份受保护时两份均不变；恢复主档属性后保存成功，恢复备份属性后主档仍可读取 |

该 runner 共 134 条断言通过、0 失败，API 完成状态无 unknown；两处只读属性均恢复
原值，21 个本轮创建的 QA 文件在证据归档后精确清理。每次 API 调用前后保留大小、
SHA-256、属性及字节副本，测试前后 PIE/dirty 状态一致。未来版本及版本不一致 fixture
只改已验证外层头和头 CRC，原始序列化 body 不变；CRC 破损 fixture 不修复其 body CRC，
测试脚本均调用封装入口，没有绕过封装把坏文件直接送入原生读取器。

以上损坏/恢复结论来自同一编辑器进程中的真实磁盘/API 测试，普通存档的早期 PIE
旅行证据另存。随后完成 Windows Development build/cook/package，并在同一包上
完成两个独立进程：第一进程以正式输入到达检查点，经真实菜单控件修改/应用设置，
再点 Save & Quit；第二进程复用同一隔离 UserDir，经 Load Checkpoint 按钮触发
OpenLevel，恢复位置、生命和已收集金币，继续接受移动输入。两进程都自然退出 0，
运行 exe 与 PAK/UTOC/UCAS 哈希相同，写后/读前/读后主档 SHA-256 一致；
该包清单不包括每个散装 DLL/文件。

实际保存与运行读回均为音量 0.95、画质 3、检查点有效、4 金币、3 条命，金币 ID
为 0/1/7/9；已收集的四枚不再出现。测试还读回实际音量和 scalability，而非只看
SaveGame 字段。写进程 121 项检查通过；读进程跨两次 Pawn 初始化共 114 项检查
通过，最终 Pawn 的 result=73，不把不同初始化的计数混为一条。原始清单、运行
结果和哈希证据留在本轮 ignored session；损坏档恢复仍未在每个打包平台重跑。

### 设置草稿与正常退出

用户设置用实际 GameUserSettings/项目设置对象，区分 pending 与已应用值；Apply 才更新运行
设置并保存，Cancel 恢复草稿，Defaults 是否立即生效按产品约定。读取实际 scalability 等
运行值，再检查重启持久化，不能只读 SaveGame 字段。PIE 的 `SaveSettings` 可写编辑器使用的
settings ini；测试前记录并恢复本轮改变的设置，独立包使用隔离的用户数据目录。

产品 SaveAndQuit 不依赖 `Automation SoftQuit`：它是非 Shipping 的开发命令，经 automation
队列处理，裸 `SoftQuit` 也不符合该命令前缀。项目可提供 `RequestGracefulExit()` 调用
`FPlatformMisc::RequestExit(false)`，返回值仅表示已请求，进程退出需另验。
该函数先检查游戏线程、非 commandlet、`IsRunningGame()`；后者允许独立游戏及编辑器
`-game`，拒绝同进程 PIE。不要用 `FApp::IsGame()` 保护编辑器，PIE 也会使它为 true。
保存成功再请求退出；失败保持菜单并提供明确的“退出且不保存”动作，不修改被保护的槽。
PIE 中函数拒绝退出须如实处理，不得为完成退出测试关闭整个编辑器。

本轮启用插件后的 PIE smoke 已通过：自然过场进入 Playing，标题/音效 handler 计数
各为 1，ViewModel 有效，封装槽处于可写状态；`RequestGracefulExit()` 返回 false，
编辑器继续响应后续调用，最后正常 StopPIE。这个结果验证了 PIE 退出保护和本轮集成，
不代表独立游戏退出成功，也不把“可写”布尔值当作保存完成。

后续独立包已分别验证两个产品退出按钮。Save & Quit 在保存成功后自然退出；
Quit Without Saving 从全新隔离 UserDir 打开菜单，实际控件改变 pending 画质但
不 Apply，点击退出后委托只执行一次、进程退出 0，外部核对主档仍不存在。
这项 18 检查的用例只覆盖无旧档情形；带旧档时还应核对主/备份文件未被修改。

ConfigSettingsToolset 作者项目/编辑器配置并可能保存 Default*.ini/.uproject，不等同玩家设置存档。
输入重映射接入正式 Enhanced Input 用户设置链：冲突/取消/恢复默认值、保存与下次启动都测。
MCP action 注入绕过 IMC；key 注入进入游戏输入但仍绕过 Slate。映射、UI 点击和焦点分开验收，
见 [UI 工作流](ue-5.9-ui-workflows.md) 与 game-production。

本地化已有原生 `EditorToolset.StringTableToolset`，不能记为完全无工具：Create/SetEntry 或
ImportFile 作者源文本，ListKeys/GetEntry 回读，GetTableId/GetNamespace 核对标识，Diff 比较候选。
导入表头至少含 `Key/SourceString`；namespace 来自资产路径，不从导入列继承。
替换导入默认关闭，bSave 默认 false；表 ID 依赖包路径，移动/重命名前检查 FText 引用。
这 9 工具处理源 StringTable，完整翻译仍需 gather → 翻译 → compile → cook，并在目标文化
启动检查实际 FText、格式参数、字体与回退；源码字符串读回不等于翻译或打包语言通过。
