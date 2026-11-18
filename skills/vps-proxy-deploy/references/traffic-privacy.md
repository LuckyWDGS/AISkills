# 国内白名单、WebRTC 与 CLI 出口保护

适用于用户主动要求的混合分流防泄漏检查或加固。先确定保留哪些 DIRECT、保护哪些程序、是否需要 WebRTC，再选择相应层；不把此方案作为普通 VPS 部署的默认安装项。

新 VPS 任务按[服务器先验收、本机先报告](local-review-and-approval.md)执行。此处是检查和获准实施的方法，不是发现缺口后自动改防火墙、浏览器或 CLI 的授权。

## 范围和证据

- 按最新用户决定处理；取消“整个 Chrome 走代理”后，不能通过浏览器 PROCESS-NAME 全量 PROXY 把它加回来。浏览器 TCP 网页仍按域名分流，可以单独保护其 UDP。
- 域名规则作用于所有请求该主机的页面。明确国内白名单仍让该服务看到直连出口；第三方页面能否读取、关联结果取决于跨域策略和服务行为。仅靠分流不能承诺任意国外页面都无法获知国内出口。
- 通用运行时的进程规则会影响全部 Node/Python/PowerShell 等任务，不只是 AI 工具。优先核对可执行文件路径、包身份、进程识别能力和用户范围；子进程、WSL/容器、虚拟环境、新程序版本另查。
- 第三方 AI 域名页是待复核的候选列表。记录获取日期，结合服务官方资料、子域、CNAME、连接日志和默认出口；不能称其穷尽遥测、登录或将来的新域名。用户要求不打开或登录服务时，用受控探测代替真实会话，报告未运行该服务。

## 规则顺序与 UDP 拒绝回退

已在 Mihomo v1.19.33 的本地故障样本及[对应源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.33/tunnel/tunnel.go)中观察到：UDP 命中的节点不支持 UDP 时会继续匹配；若越过规则尾部，可能落到 DIRECT。`PROCESS-NAME,...,PROXY` 和单个 `MATCH,PROXY` 不能单独证明故障时不直连。换核心版本后重新检查实现及故障行为。

先盘点当前 PROXY 的实际节点、嵌套组及回退成员，保护组内不能有可选 DIRECT。核对 mode=rule、有效进程识别（必要时 `find-process-mode: always`）、TUN 接管和版本支持。`strict-route` 是 TUN 的一层保护，不是核心退出后的系统防火墙。

下面是合并顺序示例，假定已核实组名为 PROXY、受保护进程为 claude.exe、浏览器为 chrome.exe；按现场替换/扩展，保留其他已授权规则，不整段覆盖现有 rules：

```yaml
rules:
  # 本机地址；应结合实际回环路径核验，不扩展为全部 LAN 或公网直连。
  - DOMAIN,localhost,DIRECT
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR6,::1/128,DIRECT,no-resolve
  # 常见 TURN TCP 端口；不包括所有 TURN over TLS。
  - AND,((NETWORK,tcp),(PROCESS-NAME,chrome.exe),(OR,((DST-PORT,3478),(DST-PORT,5349)))),PROXY
  # 保持网页 TCP 分流时可限制 QUIC；这不是所有用户的必选项。
  - AND,((NETWORK,udp),(DST-PORT,443),(PROCESS-NAME,chrome.exe)),REJECT
  - AND,((NETWORK,udp),(PROCESS-NAME,chrome.exe)),PROXY
  - AND,((NETWORK,udp),(PROCESS-NAME,chrome.exe)),REJECT
  # 每个受保护 CLI 的 UDP 拒绝必须在公网 DIRECT 白名单之前。
  - PROCESS-NAME,claude.exe,PROXY
  - AND,((NETWORK,udp),(PROCESS-NAME,claude.exe)),REJECT
  # 此处合并已有明确 DIRECT、其他合法例外；示例不代表完整平台清单。
  - DOMAIN-SUFFIX,douyin.com,DIRECT
  - DOMAIN-SUFFIX,bilibili.com,DIRECT
  - DOMAIN-SUFFIX,mp.weixin.qq.com,DIRECT
  - MATCH,PROXY
  - MATCH,REJECT
```

末尾拒绝不能替代靠前的进程 UDP 拒绝：此前若已命中国内 DIRECT，就到不了末尾。保留用户业务所需的其他 UDP 直连时明确其优先级。回环例外与公网保护分开，详见[本机回环](loopback.md)。

历史保护范围包括独立 AI 客户端、CLI、浏览器原生宿主、Node/Bun/Deno、Python/uv、curl/wget、Git HTTP 子进程及 PowerShell；这不是所有机器都应全量代理的程序清单。生成规则按当前发现结果去重，不能把“22 个进程”“275 条规则”等案例计数当作验收标准。

## CLI 入口与 DNS

需要独立 CLI 入口时，在已验证版本中可使用 loopback mixed listener 的 `proxy` 指向保护组，普通网页仍使用原入口。选当前空闲 TCP/UDP 端口、检查所有监听冲突，合并到 listeners；17890 只是历史实例端口。用实际请求确认该入口不会再落入国内 DIRECT。HTTP_PROXY/HTTPS_PROXY 指向此 HTTP 入口；仅对已确认支持的程序考虑 ALL_PROXY/SOCKS5h，保留用户原有值及回滚记录。Claude Code 按其支持的 HTTP(S) 代理配置，不把 SOCKS 变量当作保证。环境变量不等于所有应用都会遵守。

严格 CLI 模式的 NO_PROXY 通常只需要 `localhost,127.0.0.1,::1`；局域网例外按任务保留。Windows 环境变量名不区分大小写，不需要维护两套大小写互相冲突的值；旧终端和父进程可能持有旧环境，需在实际进程内验证。

应用自身的用户设置、父进程环境与系统环境是不同维护点。先只读检查谁实际拥有代理设置，再提出最小变更；获准时合并所需字段，保留 MCP、凭据和其他业务配置。禁止运行 Claude 时，只核对静态设置和受控等价探测，不能启动它查版本或声称其真实会话已经通过。

分别查看域名解析和数据连接：受保护进程命中 PROXY 不保证查询也走国外 DNS，白名单 nameserver-policy 可能仍使用国内解析器。核对 DNS 引导、代理节点域名解析、直连解析器、DNS URL 指定出口及 DoH。TUN 的 UDP/TCP 53 劫持不覆盖全部内置 DoH/DoT，不能以劫持配置宣称 DNS 全面验收。

Mihomo `any:53` 省略协议时只表示 UDP；TCP 要另查 `tcp://any:53`。Windows `strict-route` 可限制多宿主 DNS 行为，但不替代核心退出后的防火墙，并可能影响虚拟网络与 IPv6 回环；不能只因名字带“strict”就强制开启，先看[回环 A/B 经验](loopback.md)。引导 DNS、节点解析器和直连解析器分别审查；明文 bootstrap 不是“所有业务查询已泄漏”的证据。失效出口标签按 [DNS 覆写排障](dns-repair.md)复现。

核心与 DNS 的 `ipv6:false`、系统无 IPv6 默认路由、全系统公网 IPv6 阻断是三件不同的事。记录各层证据，保留 `::1`；新网卡或网络变化后重查，不能用本次无公网 IPv6 推定以后也没有。

用户要求关闭公网 IPv6 时，先检查物理、TUN、虚拟接口与实际业务依赖，再提出最小配置。物理接口 IPv6 binding、针对公网/转换地址的防火墙及 VPS 接口设置分别维护；保留回环和必要的 ULA/链路本地通信，不机械卸载整套 IPv6。只覆盖 `2000::/3` 不能代表已覆盖所有 IPv6 出网路径，还需盘点 NAT64 等转换前缀；没有对应实网环境时仍标未验证。

## WebRTC 可用与限制两种状态

| 选择 | 浏览器与核心配合 | 代价/边界 |
| --- | --- | --- |
| 限制未代理 UDP | 核对 `WebRtcIPHandling=disable_non_proxied_udp` 的有效策略；所选严格方案可同时拒绝浏览器 UDP | 可能没有 STUN 公网候选，通话受限；API 仍可能存在，不能说 WebRTC 完全删除 |
| 通过代理恢复 WebRTC | 支持 UDP 的节点、浏览器 UDP PROXY→REJECT、物理网卡保护都验证后，可按授权采用 `default_public_interface_only` | 该策略本身不强制代理，也不保证候选为国外 IP；默认物理接口仍可能暴露真实出口 |

参考 [Chromium 策略定义](https://raw.githubusercontent.com/chromium/chromium/main/components/policy/resources/templates/policy_definitions/WebRtc/WebRtcIPHandling.yaml)。检查 Chrome/Edge 各自的版本与实际有效策略、管理层覆盖和错误提示；写入注册表不等于正在运行的窗口已加载。必要时让用户正常保存并重开，再在原浏览器复测；新配置目录通过不能代替用户当前浏览器通过。

验证国内/国外 STUN，域名与数字 IP 各有样本，记录 ICE 收集是否完成、候选类型和地址、相关地址，以及相应核心连接。候选为空可能是阻断、超时或测试失败；要有正常基线与恢复样本。用无需摄像头/麦克风的 DataChannel 验证双向收发，不能代替真实音视频会话。

保留 UDP 443 拒绝能使普通 HTTPS 使用 TCP 分流，但也会影响只用该端口的实时服务。TCP 3478/5349 只覆盖常见 TURN；TURN/TLS 可能使用 443 或其他端口，白名单主机上的中继与普通 HTTPS 不能靠目的端口彻底区分。这是需报告的剩余风险。

## 核心退出后的物理网卡保护

采用按已确认程序/应用包、物理出口接口限定的出站 Block，覆盖相关协议、IPv4/IPv6 和实际网络配置文件；保留 loopback、TUN 与代理核心自身的联网路径。不要用全程序 Any 接口阻断替代，以免破坏本机服务、DNS 或代理自身。程序要直连授权国内站点时，由仍在运行的核心完成 DIRECT 出站；核心不可用时这些程序的相关请求也会失败，这是需要说明的可用性代价。

修改前记录规则身份及应用/地址/端口/接口/服务/用户过滤器，按实际程序路径和包名生成，验证 ActiveStore 与有效配置文件。已有防火墙关闭时，重新启用会激活旧规则；先审查影响，不把历史“Allow 默认值 + 39 条规则”当成整机安全基线，不覆盖用户已有默认动作。

新网卡、应用更新、独立解释器、虚拟交换机、其他 VPN 和公网 IPv6 都可能超出旧覆盖。普通失效检查不能证明防火墙控制了所有网络环境。实测方案见[故障测试](failure-testing.md)。

包身份检查不要只看可执行文件位于 `WindowsApps`。读取规则自身的 `PackageFamilyName`（应用过滤器的 `Package` 可能为空），并对实际运行的子进程使用 `GetPackageFamilyName` 等 API 核对；返回 `APPMODEL_ERROR_NO_PACKAGE`（15700）时，不能认为父应用的包规则覆盖该进程。运行时依赖包内的 Node/PowerShell 可以没有包身份，需匹配真实路径。配置覆盖缺口与实际旁路泄漏分开报告。

## 应用更新后的覆盖维护

- 发现实际安装树和独立 CLI 的完整 EXE 路径，包括更新器、MCP/SSH 辅助程序；再逐项与启用的有效规则比较。父程序受保护、同名旧版规则或一个安装目录的扫描不能代表新路径已覆盖。
- 不把所有 Node/Python/Bun/uv 或 SSH 全量阻断当作无副作用默认项。记录解释器、虚拟环境、任务宿主及其对其他项目的影响，按用户批准范围匹配。
- 若用户批准自动维护，可用登录触发与定时扫描已知安装根/物理接口的任务，以去重、可重复的方式补充规则，并留下差异日志。高权限任务的脚本、父目录及配置只能由管理员/SYSTEM写，普通用户仅有必要的读取/执行权；不要执行用户可任意改写的高权限脚本。
- 历史方案使用 SYSTEM 每分钟扫描，属于轮询补齐，**不是原子启动门禁**：更新后首次启动可能早于下一次扫描。更强的启动约束须另行设计、报告影响并获准，不能宣称周期扫描消除了全部窗口。
- 热点、新网卡、其他 VPN、程序更新或路径改变后重新盘点。Windows EXE 规则不能自动代表 WSL/容器保护，需核对各自网络模式与实际路径；未单独验收时明确列缺口，不为“补齐”停止现有全部容器。
- 核心完全退出后，依赖它完成 DIRECT 的受保护浏览器也可能无法访问国内名单。用户已暂停的白名单备用服务保持暂停；不以自动放行浏览器物理出站替代 fail-closed。
