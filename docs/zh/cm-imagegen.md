# cm-imagegen

通过你已配置的 Sub2API 或 OpenAI 兼容服务生成、编辑图片，支持多张参考图、海报、产品图、UI mockup 和批量素材；还可向支持相应能力的上游请求原生 GIF 动画和 SVG 矢量图。

## 默认模型与参数

- 图片模型：`gpt-image-2.6-sunburst`。
- 渲染画质：`quality=max`；图片规划复杂度：`complexity=high`。文生图和图生图都会显式传递。
- 默认 Images 接口：文生图 `/v1/images/generations`，参考图和编辑 `/v1/images/edits`。
- 尺寸按任务指定，收到文件后核对真实像素。方图可用 `2048x2048`，2K 横图 `2560x1440`，2K 竖图 `1440x2560`；请求尺寸仍须由上游支持。

2.5 Sunburst/Flare 保留 `quality=max`，不自动加 complexity；显式选择其他模型或参数时优先保留你的选择。服务和密钥复用本机配置，失败时不会自动切换提供方或接口。

每次生成会写本地任务台账，并在图片旁写 `.cm.json` 来源记录；命令超时或结果不明时先运行 `recover` 查看或恢复任务，不直接重发。长中文提示词可用 `--prompt-file`。

## 语言模型与 SVG 作者

这三个位置分别控制不同环节：

| 设置 | 作用 |
| --- | --- |
| `--model gpt-image-2.6-sunburst` | 选择图片模型 |
| `responses_model=gpt-6-astra`、`responses_reasoning=max` | 选择 Responses 路线的语言控制模型及推理强度 |
| `--svg-model`、`--svg-reasoning` | 选择 SVG 编写模型及其推理强度，需要上游开放模型选择权限 |

默认 Images 直调不额外调用语言控制模型。GPT-6 Astra / max 的本机配置示例和离线检查命令见 [语言控制模型说明](../../skills/cm-imagegen/README.zh-CN.md#语言控制模型)；SVG 作者不会继承这份配置。

## 可以直接这样开始

```text
$cm-imagegen 生成一张细节丰富的温室工坊，包含玻璃反光、植物、工具和清晰的空间层次，横版 2560×1440，检查实际尺寸。
```

```text
$cm-imagegen 以这张产品图为参考，只把背景改成米白色，保持产品形状、标识和光照方向。
```

```text
$cm-imagegen 请求一张原生 SVG 山地天文台徽章，使用可编辑路径和形状，并检查返回的是矢量文件。
```

```text
$cm-imagegen 请求一张小船轻摇的原生 GIF，固定镜头、4 帧、每帧 200 毫秒、无缝循环，并检查帧内容与时长。
```

## 格式与验收

PNG、JPEG、WebP 用于常规位图。GIF 需要所选模型的 GIF preview 权限；模型目录同步、白名单或账号等级不能授予格式权限。SVG 当前只支持文生图，可选作者参数需要额外的 SVG model selection 权限。

客户端会保留实际返回的格式；SVG 请求收到 PNG 会判定格式不符，单帧或重复帧 GIF 也不算成功。HTTP 200 或模型名称出现在目录里，都不能代替实际文件验收。普通尺寸可加 `--require-exact-size` 严格检查，4K 请求自动严格检查；不会用放大、裁剪或改扩展名伪造通过。

安装和完整使用方法见 [中文使用说明](../../skills/cm-imagegen/README.zh-CN.md)，参数、互斥条件及方图／横图／竖图测试见 [格式与尺寸规则](../../skills/cm-imagegen/references/formats-and-sizes.md)。技能执行规则以 [SKILL.md](../../skills/cm-imagegen/SKILL.md) 为准。

历史模型评分、画幅实测、SVG/GIF 与网关排查已集中保存在 [测试归档](../../skills/cm-imagegen/local-tests/README.md)，其中保留原图、提示词和请求记录。
