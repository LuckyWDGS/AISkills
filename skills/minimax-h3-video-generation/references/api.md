# MiniMax H3 API 约束

核对日期：2026-08-15。以下以官方文档为准；`metaso.cn` 是用户提供的兼容代理，代理的路径和响应若与官方不同，应通过 `--base-url`、`--query-base-url` 或脚本适配配置验证。

## 官方端点

- 创建：`POST https://api.minimaxi.com/v2/video_generation`
- 查询：`GET https://api.minimaxi.com/v2/query/video_generation/{task_id}`
- 鉴权：`Authorization: Bearer <API key>`
- 官方文档：[创建视频生成任务](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create)、[查询任务](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-query)

本项目默认使用用户给出的兼容代理前缀 `https://metaso.cn/api/minimax`，因此拼出 `/v2/video_generation` 和 `/v2/query/video_generation/{task_id}`。若代理只负责创建，把查询前缀改为 `https://api.minimaxi.com`；不要把 key 写进 URL。

## 创建请求

```json
{
  "model": "MiniMax-H3",
  "content": [
    {"type": "text", "text": "动作和对白提示词"},
    {"type": "image_url", "image_url": {"url": "https://.../programmer.png"}, "role": "reference_image"},
    {"type": "video_url", "video_url": {"url": "https://..."}, "role": "reference_video"},
    {"type": "audio_url", "audio_url": {"url": "https://..."}, "role": "reference_audio"}
  ],
  "resolution": "768P",
  "duration": 4,
  "ratio": "9:16"
}
```

官方已确认：

- 当前模型为 `MiniMax-H3`；`resolution` 支持 `768P`、`2K`。
- `duration` 是整数 `4`–`15` 秒，测试应优先用 `4` 秒。
- `ratio` 支持 `adaptive`、`21:9`、`16:9`、`4:3`、`1:1`、`3:4`、`9:16`。
- 文生视频（只有 `text`）的 ratio 必须是具体比例，不能用 `adaptive`。
- 图生视频首尾帧使用 `first_frame` / `last_frame` 图片；比例由输入图片决定，接口按 `adaptive` 处理，不能靠 `ratio: 9:16` 改变非竖图输入。
- 多模态参考生视频可使用 `reference_image`、`reference_video`、`reference_audio`，并可显式使用 `9:16`；参考角色图、动作参考视频和音色参考音频属于此模式。
- 首尾帧模式与多模态参考模式互斥；`first_frame/last_frame` 不能和任意 `reference_*` role 同时出现。
- 角色参考图属于 `reference_image`：项目 CLI 用 `--character programmer`、`--character boss` 从人物锁定目录解析，也支持 `--character-reference character_id=路径`。`character_id` 只保留在本地预览/任务摘要中，真正提交的 API item 仍只有标准 `image_url` + `role: reference_image`。
- 在 R2VA 中若要把上一段尾帧当作软起始锚点，应把它显式作为 `--reference-image` 传入，再传角色图；CLI 会将显式参考图排在角色图前面，便于提示词把第一张参考图定义为起始构图。它仍不是 `first_frame`，不能保证逐帧承接。
- 每次必须有一个非空 `text`，单个 text 最多 7000 字符。
- 图片：JPG/JPEG/PNG/WEBP/HEIC/HEIF，单张不超过 30 MB，尺寸 256–5760 px，宽高比 0.4–2.5。
- 参考视频：MP4/MOV，单个不超过 50 MB，单段 2–15 秒，总时长不超过 15 秒，帧率 23.976–60。
- 参考音频：WAV/MP3，单个不超过 15 MB，单段 2–15 秒，总时长不超过 15 秒。
- 请求体总大小不超过 64 MB；base64/data URI 会增加约 33% 体积，因此脚本对本地文件做保守检查。

## 查询响应

创建成功返回 `task_id`。查询的 `task.status` 枚举为：

- `queued`：排队中
- `running`：生成中
- `succeeded`：成功，视频在 `task.content.url`
- `failed`：失败，错误在 `task.error.code/message`
- `cancelled`：取消

任务记录只保留不含密钥的摘要。官方说明任务通常只可查询最近 7 天，视频下载 URL 有时效；成功后应尽快下载并保存本地副本。

## 角色参考图和硬首帧不能同时上传

这是本 Skill 的强制分流规则：

| 目标 | 实际上传 | 连续性代价 |
|---|---|---|
| 精确接上一段尾帧 | `first_frame`/`last_frame` | 不额外上传 `reference_image`；尾帧本身承担人物身份锚点 |
| 锁定角色身份并重新生成 | `reference_image`（程序员、老板等）+ 可选 `reference_video/audio` | 没有硬首帧，上一段只能作为软参考，首秒可能漂移 |

不要把老板、程序员角色图和硬首帧一起拼进 `content`。CLI 会在 `prepare` 阶段直接拒绝这种请求，并给出上述两种可选路径。

## 尾帧清晰化（离线后处理）

尾帧清晰化不是 MiniMax API 参数，也不会发起网络请求。仓库 CLI 在本地对已经提取的 `*-F-actual.png` 做以下固定处理：

- `Pillow` `Lanczos` 放大 `2×`；例如 `768×1344` 变为 `1536×2688`，原始像素比例约分后是 `4:7`，放大后仍是 `4:7`。项目请求参数可以使用 `ratio: 9:16` 表示竖屏生成方向，但尾帧增强不裁切、不补边，也不强行把实际像素改成数学 `9:16`。
- 轻度 `UnsharpMask`：半径 `0.8`、强度 `35`、阈值 `3`。
- 不做生成式超分、脸部重绘、补纹理、去背景、裁切或改构图。
- 原始帧的 SHA-256 不变；增强副本单独记录自己的 SHA-256、尺寸、倍率和处理参数。

默认 `run` / `download` 会同时保存原始尾帧和 `*-F-enhanced-2x.png`。对已有尾帧可使用：

```powershell
python scripts/minimax_video_cli.py enhance-tail `
  --input OUT\SEG03-F-actual.png `
  --output OUT\SEG03-F-enhanced-2x.png `
  --scale 2
```

增强图只是上传和检查的便利副本，不是新的事实来源。若出现过锐光晕、边缘振铃或疑似人物特征变化，应使用原始尾帧。
