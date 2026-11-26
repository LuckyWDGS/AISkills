# Claude DNS 清单

FlClash 和 Windows 分域 DNS 使用五组域名。根域和子域名均通过 `Claude-AI` 使用加密 DNS。[生效规则](../scripts/claude-network/Claude-AI.js)

| 域名范围 | 已知服务示例 |
| --- | --- |
| `claude.ai` | 网页、登录、更新、`downloads.claude.ai`、`assets.claude.ai` |
| `claude.com` | `platform.claude.com`、`releases.claude.com`、`code.claude.com` |
| `anthropic.com` | `api.anthropic.com`、`mcp-proxy.anthropic.com` |
| `claudeusercontent.com` | 工件预览、`bridge.claudeusercontent.com` |
| `claudemcpcontent.com` | MCP Apps 使用的动态小部件子域名 |

旧版 `FlClashGuard.js` 的 45 条域名中，与 Claude 对应的是上表五组。其余条目供其他 AI 服务的独立分流任务参考。Claude 桌面的 Windows 应用策略会把适用的 HTTP 请求交给 `17891`。[旧版清单](claude-legacy-ai-domains.json)

| 共享服务 | 官方文档所列用途 |
| --- | --- |
| `hcaptcha.com` 及其子域名 | 部分浏览器登录和授权 |
| `sentry.io`、Datadog 的区域上报端点 | 可选诊断和遥测 |
| `www.google.com`、`gstatic.com`、`cdnjs.cloudflare.com`、`fonts.googleapis.com`、`cdn.jsdelivr.net` | 图标、字体和工件资源 |
| `github.com`、`objects.githubusercontent.com`、`raw.githubusercontent.com`、`pypi.org`、`files.pythonhosted.org`、`registry.npmjs.org` | 按安装和扩展方式使用的代码、依赖或发布记录 |

这些共享域名记录在清单中供核对。Windows 全局 DNS 策略仅包含上表五组 Claude 域名。

[Claude Desktop 出站清单](https://claude.com/docs/third-party/claude-desktop/telemetry) · [Claude Code 网络配置](https://code.claude.com/docs/en/network-config)
