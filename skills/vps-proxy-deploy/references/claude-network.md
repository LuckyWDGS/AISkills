# Windows Claude Desktop 与 FlClash

使用 Claude Desktop 原来的应用图标。Windows 应用策略将受其管理的流量交给 `127.0.0.1:17891`，FlClash 从当前订阅生成唯一的 `Claude-AI` 策略组。脚本通过本机查询发现 Claude 安装位置、物理网卡和用户路径。[Claude Desktop 代理策略](https://claude.com/docs/third-party/claude-desktop/network-proxy#pin-a-proxy-from-managed-configuration)

## 文件

| 文件 | 用途 |
| --- | --- |
| `Claude-AI.js` | FlClash 扩展脚本，添加 `Claude-AI` 策略组、`17891` 专用代理、规则和 `127.0.0.2:53` 分域 DNS。 |
| `Install-ClaudeNetworkGuard.ps1` | 预演或启用 Claude 应用包、辅助程序、Cowork 服务的物理网卡出站规则和 Windows DNS 策略。`-UpdateDnsOnly` 更新现有 DNS 清单。 |
| `Get-ClaudeDnsNamespaces.ps1` | 从 FlClash 扩展读取 Windows DNS 策略使用的同一份域名清单。 |
| `Install-ClaudeUserTools.ps1` | 预览或安装 Claude 用户代理策略与登录监测任务。 |
| `Set-ClaudeDesktopProxy.ps1` | 给 Windows 原生 Claude 应用设置 `egressProxyUrl`。原应用图标可直接使用。 |
| `Watch-ClaudeNetwork.ps1` | 每 15 秒采样 Claude 进程树的 TCP 连接和代理、DNS 监听状态，变化时写本机日志。 |
| `FlClashRecovery.ps1` | 普通代理监听缺失时，为指定国内域名临时添加 Windows 系统代理例外，监听恢复后还原。 |
| `Test-ClaudeNetwork.ps1` | 只读查看生效保护，按需发起 HTTPS 和 DNS 探测。 |
| `Test-FlClashRecovery.ps1` | 使用模拟监听和注册表测试触发及恢复，无需停止 FlClash。 |

上述文件位于 [scripts/claude-network](../scripts/claude-network/)。

## 部署与换订阅

1. 在 FlClash 脚本库导入 `Claude-AI.js`，在订阅的「扩展 → 扩展脚本」中选中它，再从 `Claude-AI` 组选一个代理节点。每份新订阅绑定一次并检查节点选择，原订阅不需要改写。节点尚未选择时默认使用 `REJECT`。脚本遇到同名组、占用端口或不兼容的 DNS 绑定会停止应用。
2. 在脚本目录执行 `.\Install-ClaudeNetworkGuard.ps1` 预演。确认当前应用包、程序和网卡，获得对应变更授权后，在管理员 PowerShell 加 `-Apply` 执行。当前安装程序核对已知的 MSIX 程序布局和 Cowork 服务，升级后如发现差异，先检查新增或改名的组件。
3. 在日常 Windows 账户执行 `.\Install-ClaudeUserTools.ps1` 预演，确认后加 `-Apply` 安装登录时的监测任务和 Claude 用户代理策略。已有监测任务时可单独执行 `.\Set-ClaudeDesktopProxy.ps1 -Apply`。如果用户策略受权限限制，从同一账户打开管理员 PowerShell 重试。允许实机测试时，完全退出 Claude 再从原来的应用图标启动。
4. 运行 `.\Test-ClaudeNetwork.ps1` 读取监听、DNS、有效防火墙和用户策略。网络探测获授权时加 `-ProbeNetwork`，分别验证 HTTPS 显式代理和 DNS。`ClaudeDedicatedProxyConnections` 是瞬时采样，应在 Claude 有连接活动时复核并记录实际命中的 FlClash 节点。

## 当前覆盖范围

Windows 分域 DNS 及 FlClash 使用相同的五组 Claude 域名。[Claude DNS 清单](claude-dns-coverage.md)

正常运行时，由订阅已有的 `DIRECT` 规则处理 B 站、百度和公众号等直连需求。若当前订阅缺少已约定的直连项，先核对 [客户端分流](routing.md) 中的持久规则。Windows 正使用 `127.0.0.1:7890` 系统代理、没有 PAC，且连续两次监测不到普通代理监听时，恢复脚本才给这些国内站点添加 Windows 系统代理临时例外。监听恢复时撤回脚本添加的例外。只有遵循 Windows 系统代理例外的程序会受此机制影响。

独立记录正常图标冷启动、代理失效时的 Claude 阻断、国内例外恢复和现场观察到的实际出口。模拟通过只能证明恢复逻辑。Cowork 虚拟机、WSL 和远程 SSH 各自验证。如需分析旧版部署，45 个域名原表可查，导入自动绑定和核心重启仍需另外实现。[历史域名清单](claude-legacy-ai-domains.json)

## 回滚

先核对监测是否产生了 `flclash-recovery.json`。有活动例外时，恢复普通代理监听并等待监测撤回例外，再移除本次添加的监测任务。仅在确认本次新建了 `egressProxyUrl` 且值仍为本地监听地址后，移除该用户策略值。按安装记录移除本次创建的防火墙规则和 NRPT 规则，再解除订阅对 `Claude-AI.js` 的绑定。保留用户原有代理例外及策略。手动恢复前需对照当前值和日志，避免覆盖用户在故障期间的改动。
