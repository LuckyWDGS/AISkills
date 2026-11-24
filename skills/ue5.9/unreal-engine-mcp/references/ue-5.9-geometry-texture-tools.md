# UE 5.9 Preview：Geometry、StaticMesh 与 TextureGraph

适用于已核对身份的 **5.9.0 Preview / CL 60351404** 编辑器。2026-11-11
使用独立测试工程完成下列发现与实测；比较源码为 5.8.4 / CL 58902052。
这不是其他 5.9 构建的保证，也不构成 UE 5.8 live 回归。

## 新增控制与迁移的区别

只比较下列六个对应领域：安装源码的 AICallable / decorated tool 声明
**53→89**，目标编辑器也实际注册 **89** 个工具。差值 **36** 表示这些领域
多出的 MCP 声明，不能当作新增引擎系统数、全引擎差值或测试通过数。

| 领域及 live toolset | 5.8 声明 | 5.9 声明 / live 工具 | 比较所得新增 |
|---|---:|---:|---|
| `EditorToolset.MaterialToolset` | 22 | 25 | `GetStatistics`、`DiffMaterial`、`DiffFunction` |
| `EditorToolset.MaterialInstanceToolset` | 13 | 14 | `Diff` |
| `EditorToolset.StaticMeshToolset` | 16 | 22 | CollisionComplexity、QualityLevelMinLod、QualityLevelMinLodDefault 各一对 Get/Set |
| `EditorToolset.TextureToolset` | 2 | 4 | `ReadTexture`、`ExportPng` |
| `geometry_toolset.geometry_ops.GeometryTools` | 0 | 6 | box / cylinder / sphere / cone / torus / disc 的 append 工具 |
| `TextureGraphToolset.TextureGraphTools` | 0 | 18 | 参数化图、节点、接线、输入输出、验证和烘焙控制 |

大部分 Material / MI / StaticMesh / Texture 操作从 Python toolset 迁移到原生
toolset；不要把换命名空间或 snake_case→PascalCase 全算新增。GeometryScript
与 TextureGraph 引擎功能在比较的 5.8 安装中已经存在；此处新增的是 MCP 包装。
源码扫描仅覆盖选定插件中的声明并排除测试，操作仍以 live schema 为准。

## StaticMesh：能读更多资产设置，写入仍须候选验证

新增的三组控制分别解决碰撞查询方式和不同质量档位的最低 LOD：

- `Get/SetCollisionComplexity`：读取或设置 trace complexity；`CTF_UseDefault`
  继承项目的 DefaultShapeComplexity，不能据这个返回值推断实际碰撞成本。
- `Get/SetQualityLevelMinLod`：返回显式 override map；缺失档位使用 default。
  安装源码和 schema 声明 setter **合并**传入项，`-1` 清除指定 override，
  未传入档位与 default 保持原值。不是整张 map 的替换。
- `Get/SetQualityLevelMinLodDefault`：单独控制 fallback，保留各档位 override。

本次新六项中仅三个 **getter** 实测；三个 setter、LOD 重建、碰撞重建、目标
平台渲染和物理 runtime 未测。写入前复制共享网格到指定候选包，回读设置并分别
验证构建结果和实际运行行为。

**Nanite getter 存在语义变化。** 5.8 `is_nanite_enabled` 读取 Nanite settings
的 enabled 标记；5.9 `IsNaniteMesh` 调用 `HasValidNaniteData()`，返回当前网格
数据状态。live schema 明确提示刚修改设置后可能因后台 rebuild 而短暂滞后。
不要将它当成启用配置的直接回读，或立即据 false 宣称 setter 失败。

只读 fixture 为引擎 BasicShapes Cube：LOD=1、triangle=48、vertex=54、bounds
为各轴 -50…50、collision=`CTF_UseDefault`、quality overrides=`{}`、default=0、
`IsNaniteMesh=false`。材质 slot 和 material ref 也成功读回，资产 dirty 保持
false。这些是该 fixture 的读数，不能固定假设所有 Cube 都只有 12 triangles。

## Texture：可直接检查全尺寸像素并导出文件

`ReadTexture` 返回 JSON 中的 image URN，图像本体在 **raw MCP image content
block**。保留 raw result，解码 base64 并实际加载图像；不要把 URN 当 HTTP URL。
`ExportPng` 的参数是绝对 `.png` 文件路径，属于磁盘写入。其 void/null 返回值
本身不能证明产物有效，应核对文件存在、格式、尺寸和需要比较的像素。

本次对同一 256×256 Texture2D 验证：

- `GetSize` 与 `ReadTexture` 图像解码尺寸一致，raw image block 为一个。
- `ExportPng` 写入独立新文件；PNG 可完全解码，RGBA 像素与上述 MCP read 一致。
- 原纹理 dirty 在读取和导出前后均为 false；没有导入、覆盖或保存纹理资产。

安装源码优先读取有效 editor Source，缺少 Source 时走 GPU readback。这里只
验了一个有界 fixture，不据此保证 cooked-only、HDR、压缩格式、所有色彩空间、
无渲染进程或超大纹理的结果，也未将解码通过写成视觉质量验收。

## Geometry：已验证无世界副作用的基础构型写入

六项 `append_*` 全为 **write**，输入是 `DynamicMeshComponent`，在其 mesh 上
追加几何。该 toolset 没有对应 topology / bounds getter；用已发现的官方 Python
符号 `get_dynamic_mesh()`、`get_triangle_count()`、`get_vertex_count()`、
`get_mesh_bounding_box()` 回读，而非凭无错误返回验收。

本次只测 `append_box`。在 `/Engine/Transient` 下创建无 owner/world 的组件，
100×100×100 box 使 triangle **0→12**、vertex **0→24**，bounds 尺寸各轴为100。
负尺寸被 positivity 校验拒绝，triangle 数保持12。组件未注册、未附加 Actor、
未保存资产；仅释放本次 Python 引用，没有触发全局 GC。其他五种图元、组件可见性、
材质、碰撞、StaticMesh 转换与 runtime 均未验证。

此 Python 包装的 `Transform` JSON 使用下面字段；不要复用 SceneCapture 的
camera pose 格式。调用前仍读取目标 live schema：

```python
await call_tool(
    "geometry_toolset.geometry_ops.GeometryTools.append_box",
    component=component,
    transform={
        "translation": {"x": 0, "y": 0, "z": 0},
        "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
        "scale3D": {"x": 1, "y": 1, "z": 1},
    },
    dimensions={"x": 100, "y": 100, "z": 100},
)
```

此例只说明已验证的调用合同；它不创建或注册组件。生产构型应分别验收几何、
保存结果、场景呈现与运行时行为。

## TextureGraph：schema 已有完整编辑面，资产流程未验收

live 暴露18项工具，涵盖创建图、枚举/增删节点、输入参数、输出、alias、pin
值、接线、输出设置、全图读取、issue 检查和导出。`ListNodeTypes` 返回76个
不重复类，按大小写不敏感顺序排列。选节点须使用该结果中的精确 class ref。

本次按 TextureGraph 精确类搜索保存内容得到空列表，故 asset fixture 为
**missing_fixture**。`GetGraph` / `ListInputParams` / `ListOutputs`、作者写入、
validation、GPU evaluation 与 bake/export 均未测。注册18项不等于18项通过。

有两项容易误判为只读：

- `GetGraphIssues` 在 live schema 中为 execute。安装源码会初始化 targets、
  更换 error reporter 并验证；当前实现不提交 GPU batch，但仍改变内部状态。
  在候选资产上使用并检查真实 issue，不能因为名称 Get 就在原件上无条件调用。
- `ExportTextureGraph` 触发完整求值，再将所有输出写成指定 **content folder**
  中的 Texture2D；安装源码设置 overwrite textures 和 save=true，且返回 async
  result。它不是读取外部图片文件。指定独立候选输出目录，等待完成，再检查输出
  数量、实际纹理数据与 dirty/save 状态；超时不盲目重放。

## 技能集成范围

现有稳定技能已覆盖常规材质图、MI、纹理导入设置，以及网格 LOD/Nanite/材质/
凸碰撞；不要因此将旧高层 helper 当作这些5.9新路由的实现。对稳定五包 `.md` /
`.py` 的定向搜索未发现 Geometry wrappers、TextureGraph tools 或新增网格设置
的工作流。旧 texture import helper 仍使用5.8 `TextureTools` 路由。

本页补充可直接按 live schema 使用的路径，未新增批量 builder。后续可据任务
需要实现网格质量设置审计、纹理像素对照、候选程序化几何和 TextureGraph 烘焙，
每条流程完成真实写入与产物验收后再声明高层支持。

MI `Diff` 的本轮实测仅为同一路径比较返回空字符串，不证明不同实例的差异报告。
材质 statistics / material-function diff 的实测与限制另见
[材质5.9参考](../../unreal-material-artist/references/ue-5.9-material-mcp.md)。
完整连接与隔离规则见 [5.9 Preview audit](ue-5.9-preview-audit.md)。本轮未切换
稳定5.8 junction，未进行5.8 live 回归；新用法限此分支及所核对构建。
