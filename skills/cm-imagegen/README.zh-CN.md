# cm-imagegen 傻瓜式使用文档

这份文档给想在 Codex 里直接用 `cm-imagegen` 生图的人看。照着做就行。

## 这个 skill 是做什么的

`cm-imagegen` 用当前 Codex/CodexManager 的账号和接口来生成或编辑图片。

你可以让 Codex：

- 直接文生图
- 按参考图生成新图
- 修改已有图片
- 一次生成多张图
- 生成完成后直接在聊天窗口里显示图片

## 第一次使用前

先确认这个 skill 已经安装到 Codex 的技能目录。

在 PowerShell 里运行：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Skills\tools\install.ps1 -RepoRoot D:\Skills -CodexSkillsDir C:\Users\QY\.codex\skills -Skills cm-imagegen
```

然后重启 Codex。

如果不重启，Codex 可能还看不到新 skill。

## 配置要求

通常不需要额外配置。这个 skill 会自动读取：

- `C:\Users\QY\.codex\config.toml` 里的当前 `model_provider`
- 当前 provider 的 `base_url`
- `C:\Users\QY\.codex\auth.json` 里的 `OPENAI_API_KEY`

如果你用了 `cc switch`，要确保 `config.toml` 里的 `base_url` 是当前真实地址。

也可以临时指定图片接口地址：

```powershell
$env:CODEXMANAGER_IMAGE_BASE_URL="http://你的地址/v1"
```

## 在 Codex 里怎么说

最简单的用法：

```text
用 cm-imagegen 生成一张图：一只玻璃质感的小猫，坐在白色桌面上，干净产品摄影风格
```

或者：

```text
调用 cm-imagegen 生图：未来感台灯，透明材质，柔和蓝色光，方图
```

Codex 会生成图片，并把结果直接显示在聊天窗口里。

## 生成多张图

直接告诉 Codex 要几张：

```text
用 cm-imagegen 生成 4 张测试图，主题是未来感桌面小物，每张风格稍微不同
```

规则：

- 多张图会拆成多次独立请求。
- 不依赖接口的 `--n` 批量返回。
- 每完成一张，Codex 就会立刻在聊天里显示一张。
- 不需要等全部生成完才看到结果。

## 使用参考图

如果你有本地图片路径，可以这样说：

```text
用 cm-imagegen 参考这张图生成 3 个新图标：
D:\path\to\reference.png
要求：保持清爽的 3D 图标风格，但不要复制文字
```

规则：

- 每一张生成图都会单独请求。
- 每次请求都会带上同一张参考图。
- 如果你给了多张参考图，Codex 会把相关参考图都带上。

## 修改已有图片

可以这样说：

```text
用 cm-imagegen 修改这张图：
D:\path\to\input.png
只把背景换成浅蓝色工作室背景，主体不要变
```

修改类任务会尽量保留原图主体，非破坏性保存新文件。

## 失败时会怎样

如果生图失败，Codex 会用中文告诉你原因。

比如：

- 参考图文件不存在
- 接口地址不通
- 鉴权失败
- 参数不支持
- 服务临时繁忙

重试规则：

- 每张图最多尝试 3 次。
- 网络超时、连接中断、`429`、`5xx` 这类临时问题会重试。
- 文件不存在、鉴权失败、参数错误、内容安全拒绝这类明确错误不会盲目重试。
- 多图任务里，一张失败不会影响已经成功的图片。

## 图片保存在哪里

默认保存在当前工作目录的：

```text
generated-images/
```

例如这个 skill 目录里运行时，会保存到：

```text
D:\Skills\skills\cm-imagegen\generated-images\
```

Codex 会在聊天窗口里直接显示图片。你一般不需要手动找文件。

## 常见问题

### Codex 说找不到 cm-imagegen

先运行安装脚本，然后重启 Codex：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Skills\tools\install.ps1 -RepoRoot D:\Skills -CodexSkillsDir C:\Users\QY\.codex\skills -Skills cm-imagegen
```

### 地址不对或接口 404

如果你用了 `cc switch`，检查：

```text
C:\Users\QY\.codex\config.toml
```

确认当前 provider 的 `base_url` 是真实可用地址。

也可以临时指定：

```powershell
$env:CODEXMANAGER_IMAGE_BASE_URL="http://你的地址/v1"
```

### 鉴权失败 401/403

通常是当前 `auth.json` 里的 key 不被这个 CodexManager 服务接受。需要切换到正确账号、正确 provider，或修正 CodexManager 的鉴权配置。

### 聊天窗口看不到图片

让 Codex 确认最终回复里使用的是绝对路径 Markdown 图片，并且 Windows 路径用正斜杠：

```markdown
![generated image](D:/path/to/generated-images/output.png)
```

不要用相对路径，也不要用 `file://`。

## 给别人的一句话说明

在 Codex 里直接说：

```text
用 cm-imagegen 生成图片：<你的描述>
```

如果要多张：

```text
用 cm-imagegen 生成 4 张图片：<你的描述>
```

如果要参考图：

```text
用 cm-imagegen 参考这张图生成 3 张：D:\path\to\ref.png，要求：<你的描述>
```
