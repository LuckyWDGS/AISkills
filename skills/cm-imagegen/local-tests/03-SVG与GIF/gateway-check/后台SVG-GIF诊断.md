# SVG / GIF 后台检查（2026-11-07）

## 结论

当前配置存在两层 Sub2API。最近两次 SVG 和两次 GIF 测试均使用外层的 `api.5kong` 账号；内层最终使用的是 `Codex 10XPro LK`，认证类型为 **OpenAI OAuth / Pro 200**，并非 OpenAI 开发者平台 API Key。

GIF 的 400 错误已经通过跨网关请求 ID 追到这个 OAuth 账号的上游：`GIF output is not enabled for this request.`。OpenAI 官方 Images API 参考明确要求获得所选模型的 GIF preview 访问权限。当前账号页面没有可开通该权限的 SVG/GIF 开关。

SVG 请求返回 PNG 是已验证事实，但当前日志没有包含完整出站请求体，尚不能证明线上哪一层忽略了 SVG 或是否缺少上游能力。对应版本的公开源码已经支持转发 SVG 参数，不能继续沿用旧版缺少 2.6 参数的诊断。

## 当前链路与页面证据

```text
cm-imagegen
  → https://209.87.95.5:18081/v1/images/generations
  → 外层账号 #41 api.5kong（OpenAI Key）
  → https://api.5kong.online/v1/images/generations
  → 内层账号 #1 Codex 10XPro LK（OpenAI OAuth，Pro 200）
  → OAuth 账号的图片生成上游
```

- 两层页面均显示 Sub2API `v0.2.20`。
- 外层账号的模型白名单已有 `gpt-image-2.6-flare` 和 `gpt-image-2.6-sunburst`；生图尺寸档位 1K / 2K / 4K 全部允许。
- 内层账号已开启“自动透传（仅替换认证）”，页面明确提示模型白名单/映射不生效；尺寸档位也全部允许。
- 最近两次 SVG 请求在外层使用记录中分别为 06:46:33、06:47:29，输入 token 138 / 133、输出 token 均为 2058，与本轮两个案例的记录吻合。
- 最近两次 GIF 请求均出现在两层错误记录中，时间为 06:47:40、06:47:43（页面时区 America/Los_Angeles）。

第二次 GIF 的完整错误对应关系：

| 层级 | 页面错误编号 | 请求 ID | 账号与状态 |
| --- | --- | --- | --- |
| 外层 | #5162 | `c4e6d238-19ba-45dd-8ac7-eb6588b9fa73` | 账号 #41；上游 HTTP 400 |
| 内层 | #4578 | `18c203ff-ad19-487b-8f26-14bf057abbd2` | 账号 #1；上游 HTTP 400 |

外层记录的 `upstream_request_id` 正是内层请求 ID。内层记录的原始上游详情为：

```json
{"detail":"GIF output is not enabled for this request."}
```

检查没有提交账号更新、调整权限、切换模型、改变分组或发起新的付费生图请求。

## 公开代码检查与局限

公开 `v0.2.20` 标签对应提交为 `dab829a4e9b7d1cc307189aea8b0319eb29e29d0`。读取了该提交的四个相关源文件，副本及 SHA256 见 `source-manifest.json`。

- `openai_images.go:294–326`：解析 `complexity`、`output_format`、`frame_count`、`frame_duration_ms`、`svg`。
- `openai_images_direct.go:31–50`：两个 2.6 ID 使用原生图片接口；2.6 不应回退到 Responses 图片桥接。
- `openai_images_direct.go:76–105`：向 OAuth 图片上游构造请求时，保留输出格式、GIF 帧参数和 SVG 作者配置。
- `openai_images_direct.go:239–291`：返回处理主要调整模型/尺寸等元数据，未看到将 SVG 光栅化为 PNG 的逻辑。
- `openai_images.go:703–735`：API Key 路径基于原请求体改写模型并转发。

**线上部署的精确提交、运行二进制和出站 JSON 均未取得，因此公开源码是对应版本的参考，不能替代部署取证。**

## 怎样获得原生 SVG / GIF

较明确的接入方案是在现有网关内配置一个真正支持新格式的 Images API 上游，例如已有相应权限的 OpenAI 开发者平台 API Key，并将它用于独立的生图路由。单纯把当前 OAuth 账号显示为 Pro、增加模型名、同步模型列表或打开文本图片桥接，都不能授予 GIF preview 权限。

配置与验收顺序：

1. 确认上游实际支持 `gpt-image-2.6-sunburst` 的原生 SVG；GIF 还须确认该项目/凭据具有所选模型的 GIF preview 权限。
2. 若使用 OpenAI 官方开发者平台 Key，后台账号类型选 OpenAI / API Key，Base URL 使用 `https://api.openai.com`（页面说明留空也使用官方 API）。不要把 OAuth token 当作开发者平台 API Key。
3. 将该账号纳入允许生图、能被测试密钥选中的分组；保留精确模型名，避免映射到其他模型。建议独立生图分组，避免与当前文本流量混用。此次未创建或修改这些配置。
4. 按下面请求提交一次小样，逐层核对出站参数与原始响应，再验收字节格式；不能仅看 HTTP 200 或后台模型名。

SVG 请求示例：

```json
{
  "model": "gpt-image-2.6-sunburst",
  "prompt": "A clean editable vector illustration of a botanical greenhouse.",
  "n": 1,
  "size": "1024x1024",
  "quality": "max",
  "complexity": "high",
  "output_format": "svg"
}
```

解码 `data[0].b64_json` 后应得到 UTF-8 SVG XML，包含矢量路径/形状。SVG 不支持 streaming、partial images、output_compression；不能把 PNG 改扩展名作为 SVG。

官方可选的 `svg` 对象用于选择生成 SVG 的语言模型作者，例如 `svg.model` 与 `svg.reasoning.effort`。**这需要 SVG model selection 权限；没有该权限时必须省略整个对象。** 它不是启用 SVG 权限的开关，最高 reasoning 档位也取决于所选作者模型。

GIF 请求示例：

```json
{
  "model": "gpt-image-2.6-sunburst",
  "prompt": "A fixed-camera greenhouse scene with gently swaying leaves, seamless loop.",
  "n": 1,
  "size": "auto",
  "quality": "max",
  "complexity": "high",
  "output_format": "gif",
  "frame_count": 9,
  "frame_duration_ms": 200
}
```

解码后须为 GIF 文件，并验证帧数、不同帧内容、每帧时长与循环。9 帧 × 200 毫秒目标时长为 1.8 秒。当前报错是访问能力未启用；增加画质、降低帧数或更换文件名没有证据能解决它。

## 后台选项的作用边界

| 选项 | 实际作用 | 与 SVG/GIF 的关系 |
| --- | --- | --- |
| 模型白名单 / 同步支持模型 | 允许路由使用相应模型 ID | 不授予上游格式权限 |
| Codex 图片桥接策略 | 控制 `/responses` 文本请求的图片工具 | 页面说明不影响独立 Images 接口 |
| 生图结果 URL 转 base64 | 将 URL 内容回填为 base64 | 只改变传输表示，不将 PNG 变为 SVG/GIF |
| 生图尺寸档位 | 按尺寸筛选可承接请求的账号 | 不控制输出文件格式 |
| 自动透传 | 尽量保留请求/响应并替换认证 | 内层已经开启，不会新增上游权限 |

## 来源

- [外层账号管理](https://209.87.95.5:18081/admin/accounts)
- [外层错误记录](https://209.87.95.5:18081/admin/usage)
- [内层账号管理](https://api.5kong.online/admin/accounts)
- [内层错误记录](https://api.5kong.online/admin/usage)
- [OpenAI 官方生图指南：SVG](https://developers.openai.com/api/docs/guides/image-generation#generate-svg-output)
- [OpenAI 官方生图指南：GIF](https://developers.openai.com/api/docs/guides/image-generation#generate-animated-gif-output)
- [OpenAI 官方 Images API 参考：GIF preview / SVG model selection 权限](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [Sub2API v0.2.20 原生图片请求构造](https://github.com/Wei-Shaw/sub2api/blob/dab829a4e9b7d1cc307189aea8b0319eb29e29d0/backend/internal/service/openai_images_direct.go#L76)
- [本轮四次实测](../测试报告.md)
