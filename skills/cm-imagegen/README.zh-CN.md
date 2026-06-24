# cm-imagegen 中文说明

`cm-imagegen` 是这个用户环境里的默认图片生成编排 skill。它默认使用本地 CLI 调用当前 Codex 配置 provider 的兼容图片接口：文生图走 `/v1/images/generations`，图生图/参考图走 `/v1/images/edits`。默认流只尝试主通道一次；如果这一次发生非策略失败，Codex 应在 skill 层改用系统内建 `imagegen`。专用 fallback API 目前暂不参与默认路由。

## 路由顺序

默认顺序固定为：

1. 主通道兼容接口：当前 Codex 配置 provider 的 `/v1/images/generations` 或 `/v1/images/edits`。
2. 最后兜底：系统内建 `imagegen`，只在主通道单次尝试发生非策略失败后使用。

`/v1/responses + image_generation` 只作为显式测试入口保留：传 `--api responses` 才会使用。它不是默认主通道。

## 名词区分

- 系统主通道：Codex skill 层面的选择。普通生图、图生图、参考图、UI 设计图等任务优先使用 `cm-imagegen`。
- CLI 主通道：`scripts/cm_image_gen.py` 默认调用当前 Codex 配置 provider 的兼容图片接口。
- 备用接口：本地保留的专用 fallback provider 配置；当前暂不参与默认路由。
- 系统 `imagegen`：skill 层最后兜底，不是 CLI 内部 HTTP provider。

CLI 输出里的关键字段用于说明实际调用了哪里：

- `api_channel`: `configured_provider`；显式 `--api responses` 时为 `configured_provider_responses`
- `api_provider`: 实际 provider 名称
- `endpoint`: `/images/generations` 或 `/images/edits`
- `transport`: `images_json` 或 `images_multipart`
- `request_url`: 实际 HTTP 请求地址

旧字段 `provider` 和 `fallback_used` 仍保留给兼容调用方，但它们只表示 CLI 内部 provider 结果，不表示系统 skill 主通道。

## 显式 Responses 测试入口

如果需要测试工具注入，可以显式传：

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" generate --api responses --prompt "测试图"
```

这条路线会调用 `/v1/responses`，`stream: true`，并自动注入 `image_generation`。图片工具默认模型仍是 `gpt-image-2`。也可以用 `--tools` 显式透传工具数组。

## 文生图

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" generate --prompt "一张精致的产品海报，干净构图，高级布光"
```

默认会调用：

```text
POST <configured_base_url>/images/generations
```

常用参数：

```powershell
--size 1024x1024
--filename "poster.png"
--out-dir "D:\path\to\output"
--quality high
--background transparent
--output-format png
--response-format b64_json
--timeout 600
```

## 图生图或参考图

使用 `edit`，把本地图片作为编辑目标或视觉参考：

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" edit `
  --image "D:\path\to\reference.png" `
  --prompt "保留主体轮廓和姿态，重绘为精致商业插画风格"
```

默认会调用：

```text
POST <configured_base_url>/images/edits
```

多个参考图可以重复传 `--image`。

## 配置来源

主通道 base URL 来自：

1. `CODEXMANAGER_IMAGE_BASE_URL`
2. `$CODEX_HOME/config.toml` 里的当前 `model_provider`

主通道 key 来自：

1. `CODEXMANAGER_IMAGE_API_KEY`
2. provider 配置里的 `api_key` 或 key 环境变量
3. `$CODEX_HOME/auth.json` 里的 `OPENAI_API_KEY`

备用接口配置仍然可以保留在本地私有环境里，但当前默认流不会自动使用它。相关配置来源仍是：

1. `CODEXMANAGER_IMAGE_FALLBACK_BASE_URL` 和 `CODEXMANAGER_IMAGE_FALLBACK_API_KEY`
2. 本地私有 `$CODEX_HOME/cm-imagegen/fallback.json`
3. `$CODEX_HOME/auth.json` 里的 fallback 风格字段

不要把 fallback key 写进 skill 仓库、文档、提示词、日志或 handoff。

## 不生图检查配置

如果只想确认会调用哪个 provider 和 endpoint，不消耗图片请求，可以用：

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" doctor
```

或只看文生图路线：

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" check-config --operation generate
```

这两个命令不会发起网络请求，不会打印 API key，只会显示 `api_key_present`、`base_url`、`endpoint`、`transport`、`request_url` 等路由诊断字段。备用接口如果已在本地配置，也会显示为 `configured: true`，但默认流仍会标记 `used_for_default_route: false`。

如果还想确认请求会带哪些安全字段，但不显示真实 prompt 或图片 bytes，可以加：

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py" check-config --operation edit --show-payload-shape
```

这会显示 `model`、`size`、`response_format` 等字段形状；图生图会显示 `content_type: multipart/form-data`，并把图片文件部分标记为 `<redacted>`。

## 输出示例

成功时 CLI 打印 JSON：

```json
{
  "ok": true,
  "operation": "generate",
  "skill_primary_channel": "cm_image_gen_cli",
  "execution_channel": "cm_image_gen_cli",
  "api_channel": "configured_provider",
  "api_provider": "yunyi",
  "api_fallback_used": false,
  "request_url": "https://example.com/v1/images/generations",
  "provider": "yunyi",
  "fallback_used": false,
  "base_url": "https://example.com/v1",
  "endpoint": "/images/generations",
  "transport": "images_json",
  "model": "gpt-image-2",
  "paths": ["D:\\path\\to\\generated-images\\asset.png"]
}
```

默认流不再自动切到兼容 fallback provider，所以普通 `generate` / `edit` 成功结果里 `api_channel` 应保持为 `configured_provider`，`api_fallback_used` 应保持为 `false`。如果主通道失败，CLI 会直接报告这一次主通道失败；随后由 Codex 在 skill 层决定是否改用系统内建 `imagegen`。

如果兼容图片接口意外返回 SSE 流，CLI 会尝试解析 SSE 事件里的图片结果。只有找到图片 base64 或 URL 时才会保存图片；如果 SSE 里没有图片，会输出 `sse_event_count`、`sse_event_types`、`sse_json_payload_count`、`sse_image_item_count` 等诊断。

## 失败处理

- 默认主通道只尝试一次，不做额外自动重试。
- 缺 key、缺 base URL、HTTP 400 参数错误、模型不支持、缺本地图片等不做盲目重试。
- 策略或安全拒绝不允许切换路线绕过。
- 主通道单次尝试发生非策略失败后，Codex 可以使用系统内建 `imagegen` 作为最后兜底。

## 多张图片

后端不一定可靠支持 `n`。如果用户要 4 张图，推荐运行 4 次独立 CLI 调用，并用不同文件名保存。带参考图时，每次调用都重复传同一组 `--image`。

## 离线测试

开发或修改脚本后，可以运行不访问网络的 mock 测试：

```powershell
python "$HOME\.codex\skills\cm-imagegen\scripts\test_cm_image_gen.py"
```

当前覆盖默认 `/images/*` 路由、单次主通道失败行为、SSE 图片恢复、无图片 JSON 诊断和 `doctor` 路由预览。
