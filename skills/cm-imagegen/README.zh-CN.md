# cm-imagegen：Sub2API 单服务版

只需安装本技能即可调用生图脚本，不依赖另一个生图 skill。它不是图片模型本体；使用者仍需 Python 3.10+、可访问的 Sub2API 地址、自己的有效主 API key，以及有生图权限和可用上游的分组。

## 安装

把整个 `cm-imagegen` 文件夹复制到 `$CODEX_HOME/skills/`，未设置 `CODEX_HOME` 时为 `~/.codex/skills/`。新开 Codex 会话使用 `$cm-imagegen`。现有 Codex 已配置 Sub2API 时可直接复用配置，无需复制任何人的密钥。

核心请求仅使用 Python 标准库。安装 `Pillow` 可检查 JPEG/WebP 尺寸并运行完整测试；`requests` 仅用于可选的传输诊断。

安装可选依赖：`python -m pip install -r requirements-optional.txt`。

## 连接现有 Sub2API

优先使用 Codex 已有的 `config.toml` 当前 provider 和主 key。支持 provider 内的 `api_key`/`key`、`env_key`/`api_key_env_var` 指定的环境变量，以及 `auth.json` 的 `OPENAI_API_KEY`。不会把网页登录 OAuth token 自动当成 Sub2API key。

若需单独设置当前进程的生图连接，可使用以下占位示例（换成自己的服务地址与主 key，不要将真实 key 发给他人）：

```powershell
$env:CODEXMANAGER_IMAGE_BASE_URL = 'https://your-sub2api.example/v1'
$env:CODEXMANAGER_IMAGE_API_KEY = '<your-own-primary-key>'
```

脚本只使用这一组主连接；没有备用接口、备用密钥或自动切换服务入口。包内不含任何真实 API 地址或密钥。

## 模型与默认路由

默认使用 Images API，命令中显式写 `--api images`：文生图调用 `/v1/images/generations`（JSON），图生图/参考图调用 `/v1/images/edits`（multipart 上传）。这些路径以服务 base URL 已包含 `/v1` 为前提；脚本会保留服务自己的 base 前缀。

默认图片模型为 `gpt-image-2.5-sunburst`，最高画质为 `quality=max`。Sunburst/Flare 未指定画质时也使用 `max`；可用 `--model`、`--quality` 显式覆盖。其他模型不自动套用 `max`。Images 没有独立的 `reasoning.effort` 参数，最高画质不能等同于已验证的最高推理强度。

可选的 `$CODEX_HOME/cm-imagegen/controller.json` 只存路由和控制器偏好，不存地址/key；缺少它仍可工作。使用 Images 时将 `api` 设为 `images`，最小配置为 `{"api":"images"}`；旧 Responses 配置仍可读取，显式 `--api images` 优先于配置。失败时不会自动切换接口。

仅在明确需要 Responses 时使用 `--api responses`；其 `--responses-model` 和 `--responses-reasoning` 与图片模型/画质独立，服务接受的推理档位可能不同。不要为此修改聊天模型或全局推理设置。

## 检查和使用

在本技能目录中执行：

```powershell
# 离线：查看配置和请求字段，不显示 key
python scripts/cm_image_gen.py doctor --api images --show-payload-shape

# 联网读取模型目录，不生成图片
python scripts/cm_image_gen.py doctor --api images --check-model

# 真实生图，会使用该服务额度；诊断时只请求一次
python scripts/cm_image_gen.py generate --api images --model gpt-image-2.5-sunburst --quality max --prompt 'A blue ceramic mug on a plain white background. No text.' --max-attempts 1 --out-dir './generated-images'

# 使用自己的参考图
python scripts/cm_image_gen.py edit --api images --model gpt-image-2.5-sunburst --quality max --image './reference.png' --prompt 'Change only the mug color to orange.' --out-dir './generated-images'
```

成功标准是 `ok=true` 且 `paths[]` 指向可打开的图片。目录检查通过、HTTP 200、模型输出了一段文字，都不能代替实际图片结果。

## Sub2API 必要条件

- 主 key 有效、余额/配额可用，绑定正确的 OpenAI 分组。
- 分组允许图片生成（`allow_image_generation`），并有支持相应图片工具的健康上游账号。
- 服务的 Images 接口可用，支持请求的图片模型和 `quality=max`。仅 Responses 模式还需支持对应控制模型。
- HTTPS 证书可验证，网络和反向代理允许长时间流式响应。

默认请求直接调用 Images 接口，不需要依赖服务端给普通聊天自动注入工具。只有文本转发能力的上游不能通过安装 skill 获得生图能力。

## 失败与测试

默认最多请求 3 次（间隔 5/15 秒），缺配置、鉴权、参数、权限和策略问题不盲目重试。流中断但任务尚未结束时不重复提交。详细规则见 `SKILL.md`。

安装 Pillow 后可运行离线测试：`python -m unittest discover -s scripts -p "test_*.py"`。离线测试不证明真实服务可用；实测成功仅证明当时的配置与请求可用，不能承诺所有用户每次成功。
