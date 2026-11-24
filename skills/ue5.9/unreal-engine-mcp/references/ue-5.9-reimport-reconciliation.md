# 模块场景重导入与手工调整

用 [reconcile_scene_import.py](../scripts/reconcile_scene_import.py) 对照上一次
认可的源版本、修订后的源版本和 UE 当前读数。适用于 glTF 分件场景、UE 厘米摆位表
和 Interchange 材质实例。发现新网格、换父材质或有意改过的关卡摆位时，可保留实例
和设计师修改，逐项决定如何合并。

## 在替换导入前保留现场

保存旧源清单。首次导入时记录 Interchange 返回的完整对象路径及放置时返回的 actor
路径。每个实例用独立 ID，同一种网格可以对应多把椅子。资产映射可直接采用首次导入
的 `[{"refPath":"…"}]`，也可以提供 `{"源名称":"/Game/路径/对象.对象"}`。后者可以
区分不同文件夹中的同名对象。实例映射使用
`{"实例ID":{"refPath":"/Game/…/L_Room.L_Room:PersistentLevel.StaticMeshActor_0"}}`。

先在当前关卡采集设计师的摆位、组件覆盖和 MI 值。把修订文件导入独立候选目录验证网
格、贴图和槽位。在已经重导过的正式库上采集只能看见替换后的状态。没有旧源或替换前
快照时，不能判断被覆盖的手调原来是什么。可以在独立目的目录重建旧版本，当前值有疑
问的项保留给人工核对。

源适配器从 `.gltf` 或 GLB 的 JSON chunk 读取线性 RGBA、roughness、metallic、可选
的 KHR specular，以及 baseColorTexture 的 texture → image → UE 对象路径。摆位表
为
`{"groups":[{"name":"Shelf01","meshName":"SM_Shelf","folder":"Furniture","pivotUE":[100,20,80],"slots":["Oak"]}]}`。
`rotationUE` 可按 pitch/yaw/roll 传对象，单位为度，`scaleUE` 可按 x/y/z 传对象。
默认旋转为零，缩放为一。不同坐标约定的导出器先转到 UE 世界厘米。

若 glTF 材质叫 `Oak`、UE 槽叫 `MI_Oak`，传 `--slot-prefix MI_`。可用导入结果中的
`MI_Oak` 对象，也可显式映射 `{"Oak":"/Game/Rooms/Library/MI_Oak.MI_Oak"}`。已带
前缀的槽名只使用一次。两个名称指向不同资产时，先按实际导入记录消除映射歧义。

标准 glTF 允许省略材质与图像的 `name`。可在资产映射里用 `material:0` 或
`image:0` 指向对应 UE 对象，索引分别取自本版 glTF 的 `materials` 和 `images` 数
组。摆位表中出现的具名 UE 槽也要能解析到该材质。源文件重排索引时，为新版本单独核
对映射。此适配器读标准 `texture.source`。需要按其他编码扩展解析贴图时，先扩展源
映射并复核结果。

采集范围由旧源、新源列出的字段决定。正式替换前，对有手调的 MI 另存完整资产副本或
使用项目版本控制，并记录组件绑定、父材质、额外参数和静态开关。只留此次差异报告无
法恢复未列入源清单的美术调整。

```powershell
$tool = 'scripts/reconcile_scene_import.py'
$roomMap = '/Game/Rooms/L_Room'
$live = @('--url', $env:UNREAL_MCP_URL, '--project', $env:UE_MCP_PROJECT, '--pid', $editorProcessId, '--level', $roomMap)
python $tool source --gltf old/room.glb --placement old/placement.json --assets imports.json --actors instances.json --level $roomMap --label-prefix Room_ --folder-prefix Room --slot-prefix MI_ --out base.json
python $tool source --gltf new/room.glb --placement new/placement.json --assets imports.json --actors instances.json --level $roomMap --label-prefix Room_ --folder-prefix Room --slot-prefix MI_ --out source.json
python $tool capture @live --base base.json --source source.json --out current.json
python $tool plan --base base.json --source source.json --current current.json --out preview.json
```

在技能目录运行。用身份检查确认的离屏编辑器 PID 设置 `$editorProcessId`。候选库新
建的对象可从注册表查回，再显式登记映射。缺少一个模块的 actor 路径时，报告该实
例，先检查关卡中是否已有对应物件。

## 阅读差异并应用选定字段

| 结果 | 实际含义与处理 |
| --- | --- |
| `equal` | UE 当前值与修订值一致。在汇总计数内，重复运行无需写入。 |
| `keep_editor` | 两版源值相同，编辑器有独立改动，保留现状。 |
| `source_update` | 编辑器仍为旧源值，修订源提供了不同值。检查该行的 `selectable`。 |
| `conflict` | 源与编辑器都改过，而且结果不同。报告列出三个实际值，由美术决定取舍。 |
| `review_structure` | 字段或对象新增、缺失、身份重复、组件或槽位不明确。先修身份或映射再重采。 |

场景比较加载的实例、标签、文件夹、世界变换、网格对象、每个具名槽的实际材质，以及
组件按槽名解析的覆盖。几何拓扑、LOD、碰撞、外观和未加载的 World Partition 区域需
另行验收。MI 比较显式覆盖，无覆盖时读取有效值。此适配器可写范围限于已验证的
Interchange Substrate glTF 父材质的全局 scalar、vector 和 texture 参数。其他父材
质、层参数、结构项及关卡摆位可在报告中检查。执行器没有生成 actor 或整体替换材质
的步骤。

从 `preview.json` 的 `differences` 复制选定行的完整 ID。不同目录的同名 MI 会得到
不同 ID。下面的命令只更新一项底色。

```powershell
$field = 'materials|/Game/Rooms/Library/MI_Oak.MI_Oak|Vector:BaseColorFactor'
python $tool apply @live --root /Game/Rooms/Library --plan preview.json --select $field --out applied.json
```

每个额外字段再传一次 `--select`。先预检全部选择，再在每项写前读取干净状态、精确
对象路径、父材质和当前有效值。编辑器值与预览不同会中止，已经达到修订值则记录
`already_current`。修改后复读有效值，只保存对应 MI 并验证包已 clean。输出文件在
尝试写入及保存前记录进度。若中断或超时，保留该报告，先从编辑器查包和参数，重新采
集后再处理剩余项。在独立编辑窗口串行执行，避免其他作者同时编辑同一包。两次跨进程
RPC 之间没有引擎级写锁。数值比较绝对容差为 `0.0001`。已知由美术专管的字段可以直
接从选择中排除，即使其数值恰好等于旧源。

## 在 5.9 Preview 验证的范围

- 重新读取厨房候选关卡的 58 个模块、219 个具名槽、56 个 MI 和 177 个 MI 参数，
  916 个比较字段均与修订清单相符，包括 8 个 base-color 贴图引用。旧记录中的四个
  底色逐项回放为源更新，当前 UE 读值均已匹配。
- 在独立临时目录将一个真实 GLB 首次导入并连续替换两次。两次调用各只返回网格，注
  册表均保留同样的网格和 MI。用一份独立 MI 模拟正式材质，报告识别出两项源更新、
  一项手调和一项双方冲突。预览后再改粗糙度，使整批预检拒绝了陈旧选择。
- 只选择底色保存，再通过 `ReloadAsset` 读回。人工保留的 metallic、roughness 和
  specular 值均维持原值，第二次执行为零写入。场景内的 73 个 actor 身份前后一致。
  测试完成后清除了自有临时资产。
- 将带纹理的橡木 MI 复制至独立目录，选中底色贴图、粗糙度和颜色三项。三个原生
  setter、有效值 getter、指定保存和重载回读全部通过。再次运行三个字段均为
  `already_current`。无项目身份的计划在整批写前被拒绝，测试前后的 dirty 包集合相
  同。这项检查验证的是 UE 对象引用和参数值，贴图外观仍需在场景光照下实渲。

## 验证记录

构建：UE 5.9.0 Preview / CL 60351404。

**在替换导入前保留现场**

- 两个源版本都映射到本次要核对的同一套正式对象。

**阅读差异并应用选定字段**

- 写入限定为这次指定的资产目录和当前项目/关卡的实采计划。
