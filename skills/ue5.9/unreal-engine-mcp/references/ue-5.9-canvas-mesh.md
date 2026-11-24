# UE 5.9 Canvas：本地 Mesh 生成与导入

2026-11-16，5.9.0 Preview / CL 60351404、Canvas v0.21.0 实测。
先读 [Canvas 连接与生成边界](ue-5.9-canvas-generation-render.md)。本页验证的是
GeometryScript 程序化建模，不是图片/文字推理生成 3D；本次
`list_models({"category":"mesh-generator"})` 为空，未调用外部 Mesh 模型或 Claude。

## 选择有实际执行能力的路线

- **AI Mesh Generator** 依赖可执行的 provider/model binding。以实时 `list_models`
  为准；按钮、注册表中的模型名、已配置的普通生图 API 都不证明能生成 Mesh。
- **Mesh Op** 是本地 GeometryScript：图元、多边形挤出、布尔、法线、UV、减面等。
  `createsGeometry=true` 的操作可以从空网格开始；其他操作按目录要求提供输入。
  它不需要云模型，但需要正确连接 UE Bridge。本次未下载可选组件或模型权重。
- 当前流程不匹配库模板时，在新的 Graph card 内编图。顶层 Canvas 节点没有可连接
  pins；不要覆盖用户已有渲染模板。`canvasOutput` 的入边决定输出名称与类型。

## Mesh Op 的动态参数

先核对 UE 的完整身份和绝对项目，再读取该实例的 `ListMeshOps`、`RunMeshOps`
schema；按 library 限定目录。只读目录不代表所有操作已测试。

v0.21.0 的 `find_node_kinds` / 新节点只给出 `meshOp` 基础字段。仅写 operation ID
不足以让未初始化目录的前端获得操作的参数/输入描述。本次对照该版本前端适配器，
用原生 `write_graph` 写入以下字段后成功执行：

```python
op = next(x for x in live_ops["ops"]
          if x["id"] == "Primitives.AppendSimpleExtrudePolygon")
params = {
    "meshOp": op["id"],
    "meshOpSchema": op,  # 原样使用目标 UE 的目录项，不虚构能力
    "listItems": {"PolygonVertices": ccw_points},
    "Height": 16,
    "HeightSteps": 0,
    "bCapped": True,
    "Origin": "Center",
    "Transform.Rotation": [0, 0, -90],
    "mcpUrl": verified_editor_url,
}
```

`ccw_points` 是不重复端点的逆时针 `[[x,y], ...]`；列表参数放在
`listItems.<输入名>`。标量/向量参数直接使用目录中的 dotted name，不嵌套成
`args`。`meshOpSchema` 是操作描述，`RunMeshOps` 执行时仍在 UE 校验真实操作。
本次通用参数检查器曾对这些动态字段产生 unknown-param warning；已通过适配器
源码、节点参数读回、实际 GLB 及 UE 资产验证它们被消费。这不是忽略其他 warning
或跨版本沿用内部字段的通行证。未取得一致合同则保留图，不盲目执行。

## 已完成结果必须创建修订

原生图执行产生结果后，其内容会锁定；`write_graph` 会明确拒绝修改。该锁与
分享过程的临时锁不是同一机制，不绕过或直接改存储。调用
`prepare_graph_version`，用返回的 `canvasId` 编辑、`nodeId` 执行，保留源结果。
复制图的内部节点 ID 可能相同，后续读/写/验收必须携带准确的 canvasId。
本次在检查首版星尖朝下后，按此路线修正旋转，并保留初版。

`run_node` 仅提交一次。异步返回后按同一个节点核对实际结果；不要因工具提示
“started”就宣称已完成，也不要重新 run 代替状态查询。

## 导入与验收

本次原生图：`meshOp → canvasOutput.Mesh`，并将 mesh 接到
`createStaticMeshAsset → canvasOutput.UE Asset Path`。
导入使用独立测试目标、`skipDialog=true`、`allowOverwrite=false`、`meshType=Static`。
该节点会导入并保存资产，不能当成纯预览；不得连入自动反复执行的生产图而不评估
它的写入行为。

导入返回路径会包括额外的资产名目录、`StaticMeshes/`，材质在 `Materials/`。
使用实际返回路径，不从 Destination Path 和 Asset Name 拼接最终文件。需要
UObject 引用的 `StaticMeshToolset` 用 `/Package/Asset.Asset` 完整对象路径；
`CaptureAssetImage` 的 assetPath 则接受 package path。

本次验收：

- 原生 Graph 生成 GLB，UE generator/version 可读；36 triangles、42 导出 vertices，
  按坐标合并为 20 vertices/54 edges，每边连接两面、Euler=2、无零面积三角形、
  正体积，包含 normals 和 UV0。不能把属性缝拆分的顶点误判成网格破洞。
- UE StaticMesh 读回 36 triangles、42 vertices、LOD=1，尺寸约
  95.11×16×90.45 cm，导入一个白色 unlit 材质；256×256 原生资产缩略图实看通过。
  这是几何 fixture，没有证明 PBR 美术、碰撞、LOD/Nanite 或游戏 runtime。
- 原地图、编辑相机、actor/selection、dirty packages 和已打开资产列表前后一致；
  新 Mesh/MI 保存在专属目录，未放进用户关卡。
- Canvas 输出检查曾只返回 GLB，即使节点已有 `screenshotByVersion`。使用准确
  version 对应的截图文件检查，不把 GLB 路径当成图像。交互 viewer 的 mesh control
  曾报告 `ready=false/camera=null`，因此未宣称交互旋转或正背侧视图验收通过。

原始调用、失败首版、修订 ID、文件哈希及机器路径保存在忽略的 session；交付 GLB、
原生缩略图和报告单独归档。AI Mesh 生成与 UE 5.8 live 回归仍未覆盖。

## 复杂装配：分批原生建模

2026-11-17，同一构建扩展到包含 132 个构件的飞船。变截面机身/座舱使用
`Primitives.AppendSweepPolygon`，机翼用 `AppendSimpleExtrudePolygon`，发动机
组合 cylinder/cone/torus 和 `AppendRevolvePolygon`。扫掠的二维截面位于局部
YZ，路径变换的 X 沿路径；`SweepPath` 的 transform 列表项使用
`{Rotation: [pitch,yaw,roll], Translation: [x,y,z], Scale3D: [sx,sy,sz]}`。
先用小样确认旋转方向：本次沿 XY 挤出的尾翼需要 Roll=-90 才朝向 +Z，+90
的首版向下。不能只看参数名断定方向正确。

很长的 Canvas Mesh Op 串联会反复导出、导入中间 GLB。本次 133 个操作节点的
长链中途失败，返回 `Unreal ended the call without a result`，同时 UE 日志存在
Interchange 资产路径名称预算警告。没有证明警告是唯一根因，也没有修改引擎。
保留失败图后，使用该实例已暴露的 bare tool `RunMeshOps`，以短 `outputName`
分五批生成完整结果成功；它仍是官方 Canvas Bridge MCP，不是自制桥或 UI 降级。

适合复杂装配的已验证调用规则：

- 每次 `ops` 最多 32 项；本次每批不超过 28 项，为最后的查询留空间。这里只是
  本次批量大小，勿把 28 写成引擎限制。首批从空网格开始需 `createsGeometry`。
- 后批使用上一批实际返回的 `path` 和该 GLB 的 SHA-256 `inputHash`；成功结果的
  `inputSource=sidecar` 确认命中了无损 DynamicMesh 中间数据。保存每批结果；失败
  后只处理未完成批，不盲目重跑已完成写入。显式验证拒绝与未知完成状态分别处理。
- 操作使用 `{"op": live_id, "args": dotted_parameters, "inputs": ...}`。
  列表输入为 `{"PolygonVertices": {"items": points}}`，不同于 Canvas 节点的
  `listItems` 字段。以本次 live `ListMeshOps` 的参数、输入、`data`、`writes`
  和 `query` 标志决定顺序。
- 产生列表的操作必须放在该调用末尾。本次把
  `Query.GetAllDegenerateTriangleIDs` 放在其他查询之前被明确拒绝；调整到末尾后
  执行通过。不能因为名称带 Query 就忽略它的列表输出合同。
- `PrimitiveOptions.MaterialID` 可以保留不同分区，但每次导出会把实际使用的 ID
  压紧为材质 slots。本次按 ID 顺序逐组追加，始终保留之前各组，最终六分区完整；
  任意跳号/删组/重排后必须重新检查 slot 映射，不能把旧 ID 当永久标识。
- 完整 GLB 再用 `meshInput`（`meshSource="file"`、`sourcePath`）接
  `createStaticMeshAsset`，运行整个有输出的 Graph。`write_graph` 只存路径，
  不导入文件、不产生可见结果。最终修订仍使用 `prepare_graph_version`。

原生操作最初给出占位材质。本次对导出 glTF 的六个材质设置金属度、粗糙度、
基础色及发光，再由原生 Canvas 导入；前后几何 binary hash 一致。这个步骤是
**材质整理**，不是 AI 生成或纹理烘焙，也不是 Mesh Op 自动生成了 PBR 艺术。
导入后读取六个 MI 的 BaseColorFactor、MetallicFactor、RoughnessFactor 及
EmissiveStrength，与 GLB 对照；不能仅检查 slot 数量。

## 复杂网格验收与 Nanite 计数

最终飞船 GLB 为 11,584 triangles、12,910 导出 vertices、6 个材质分区；原生
DynamicMesh 为 6,024 vertices，差异来自属性接缝拆点。原生查询得到 132 个
connected components、0 个开放边、0 个退化三角形、closed=true。这里的闭合
仅表示每个构件闭合：装配中的相交壳体没有做整体布尔融合，不能据此宣称可制造
实体、无自交或已经有游戏碰撞。UV0/法线存在也不等于已做唯一 UV 图集和贴图。

导入遵循项目设置，可能自动启用 Nanite。`StaticMeshToolset.GetTriangleCount`
和 `GetVertexCount` 读取传统 LOD render resources；对 Nanite 资产可能看到
fallback 数量，不能与 GLB 原始三角数直接比较。本次首版读到 2,090 triangles，
`IsNaniteMesh=true`，首次离屏截图也出现较粗细节，随后截图恢复；后者只支持
资源/streaming 时序的判断，不是已确诊根因。

本次约 1.2 万面的最终静态原型使用原生
`SetNaniteEnabled(mesh, bEnabled=false)`，待 rebuild 后回读
`IsNaniteMesh=false`，LOD0 triangles/vertices 与 GLB 完全相等，再保存指定 Mesh。
这是此候选的选择，不是要求对其他资产关闭 Nanite。保留 Nanite 时应另查源几何
和稳定后的画面，分别报告 source、fallback、实际渲染证据。

复杂模型的视觉验收使用独立 `-RenderOffscreen` 编辑器和新展示地图，按
显式相机 pose 调用 `SceneCaptureToolset.Capture`。本次 1600×1200 的前上、
后上、侧面 Lit 和 Normal 图实际解码并检查，修正了尾翼和悬空装饰；最终
Mesh/六个 MI/展示地图均 scoped 保存。用户原实例的地图、视口、PIE、actors、
selection、open assets、dirty packages 前后一致。参数与图片证据留在 session。
该结果是有材质的静态原型；没有驾驶舱内饰、骨骼/可动部件、飞行逻辑、碰撞或
打包运行验收。蓝色座舱为不透明高光材质，不据此声称验证了透明玻璃或折射。
