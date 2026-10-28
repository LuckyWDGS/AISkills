# cm-imagegen

通过已配置的 **Sub2API / OpenAI-compatible 服务**，在 Codex 中生成和编辑图片。

本技能位于 [LuckyWDGS/AISkills](https://github.com/LuckyWDGS/AISkills) 的 `skills/cm-imagegen/`，该目录包含完整的 `SKILL.md`、脚本和参考文档。它不需要另一个生图 skill，但使用者仍需自己的有效服务地址、主 API key、图片生成权限和可用额度。

## 功能

- 文生图、图生图和多张参考图。
- 默认使用 Responses API 的 `image_generation` 工具；可显式使用同一服务的 Images API。
- 只使用一个主服务，没有备用 API/key，也不会自动切换其他服务。
- 同一请求最多尝试 3 次，保留失败原因；未结束的任务和流中断不会盲目重复提交。
- 保存图片到本地，去除 SSE 重复结果，并检查输出尺寸。
- 主连接复用现有 Codex 配置，也支持进程环境变量。仓库不包含真实地址、密钥或个人账号文件。

## 安装

需要 Python 3.10+。以下命令只安装 `cm-imagegen`；已有本仓库时进入现有目录后执行安装步骤即可。

Windows PowerShell：

```powershell
git clone https://github.com/LuckyWDGS/AISkills.git
Set-Location AISkills
powershell -ExecutionPolicy Bypass -File ./tools/install.ps1 -Skills cm-imagegen
```

macOS / Linux：

```bash
git clone https://github.com/LuckyWDGS/AISkills.git
cd AISkills
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$PWD/skills/cm-imagegen" "${CODEX_HOME:-$HOME/.codex}/skills/cm-imagegen"
```

已有同名技能目录时，先备份再安装；Windows 安装脚本可加 `-Replace` 自动备份现有实体目录。也可下载压缩包，只把 `cm-imagegen` 文件夹复制到自己的 Codex skills 目录。保留仓库目录以免符号链接失效。重新启动 Codex 后可用 `$cm-imagegen` 调用。

核心 API 请求只依赖 Python 标准库。完整离线测试和 JPEG/WebP 尺寸检查需要 Pillow，可选的 requests 传输诊断需要 requests。先进入 `skills/cm-imagegen`；以下使用、诊断和测试命令都在该技能目录运行：

```bash
cd skills/cm-imagegen
python -m pip install -r requirements-optional.txt
```

## 使用

如果 Codex 已连接到支持图片工具的 Sub2API，可直接复用主配置。其他连接方式、模型设置和排障见 [中文使用说明](README.zh-CN.md)。

```bash
# 本地诊断，不联网、不生成图片
python scripts/cm_image_gen.py doctor --show-payload-shape

# 读取模型目录，不生成图片
python scripts/cm_image_gen.py doctor --check-model

# 真实生成，会使用服务额度
python scripts/cm_image_gen.py generate --prompt "A blue ceramic mug on a plain white background" --out-dir ./generated-images

# 图生图
python scripts/cm_image_gen.py edit --image ./reference.png --prompt "Change only the mug color to orange" --out-dir ./generated-images
```

默认图片模型为 `gpt-image-2.5-sunburst`。`--model` 选择图片模型，`--responses-model` 选择控制模型；实际支持情况以自己的服务为准。没有外部 `controller.json` 也能运行。

## 验证与边界

运行现有 50 项离线测试：

```bash
python -m unittest discover -s scripts -p "test_*.py"
```

GitHub Actions 在 Python 3.10 和 3.12 上运行同一套离线测试，不配置 API key、不调用真实生图服务。

2026-10-25 的 Sub2API 文生图与隔离环境图生图实测均成功。该次服务拒绝 `ultra`，接受 `max`；这是当时的服务行为，不代表所有部署都相同。

**技能不能保证每次请求成功或输出精确尺寸。** 实测请求 1024×1024，返回 1374×1145。需要精确尺寸时加 `--require-exact-size`，不匹配会报错；4K 请求自动严格检查。服务权限、配额、上游账号和网络仍由使用者自己的环境决定。

## 文档

- [技能入口](SKILL.md)
- [完整中文说明](README.zh-CN.md)
- [CLI 参数](references/cli.md)
- [请求与响应](references/image-api.md)
- [Sub2API 连接检查](references/codex-network.md)
- [提示词建议](references/prompting.md) / [示例](references/sample-prompts.md)
