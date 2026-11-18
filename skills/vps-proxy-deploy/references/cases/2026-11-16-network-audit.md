# 2026-11-16 网络过滤、检测站与防泄漏审计案例

这是历史观察，不是当前机器状态，也不是可直接部署的模板。真实服务器、出口地址、私有订阅、认证参数、控制器和进程路径均已脱敏。用 VPS A 表示故障目标、VPS B 表示可用对照；文中的 `203.0.113.10`（A）、`198.51.100.20`（B）仅为文档保留地址，不可用于连接。

目录：

- [用户决定与范围](#用户决定与范围)
- [大陆方向 TCP 对照](#大陆方向-tcp-对照)
- [节点 A 的 HTTP 与 DNS](#节点-a-的-http-与-dns)
- [实际 Chrome 的结果](#实际-chrome-的结果)
- [配置问题与优先级](#配置问题与优先级)
- [未验证项与收尾](#未验证项与收尾)

## 用户决定与范围

- 保留抖音、B站、公众号及已有明确国内 DIRECT 名单，包括当时的微信/QQ、远控、网盘、购物、会议、模拟器、小红书、快手等；删除泛化的国内域名/IP兜底直连。新任务仍按当次授权选择类别。
- 用户先选择 Chrome 全代理，后来明确取消；最终保留按域名分流，不能把旧选择重新安装。
- 用户希望 WebRTC 可用并尽量防泄漏；早期“没有公网地址”或全UDP拒绝的结果不能代替恢复功能后的验证。
- 保留 `localhost`、`127.0.0.1`、`::1` 本机通信。UE/Zen 的 DDC 崩溃不能仅因使用本机代理归因；回环例外与实际端口可达性分开，历史故障仍未证明完全修复。
- 本案例这一轮要求先检查代理、比较方案，不修改正式配置，不登录实际 Claude。检测站自行发出的 Claude/Anthropic trace 请求已记入边界；未执行真实账号会话。
- 随后的“记录技能、研究技术”仅更新资料；不是部署、升级、切换节点、故障注入或 Git 推送授权。

## 大陆方向 TCP 对照

观察窗口：2026-11-16 20:39–20:40，America/Los_Angeles（PST，UTC−08:00）。服务端 A 使用 Xray 26.9.30，本机 Mihomo 1.19.33。

通过 Globalping 初次测量 ID 复用相同九个探针，并逐项比较元数据。每个探针每项重复三次。大陆六探针覆盖电信（重庆、广州）、联通（武汉、西安）、移动（武汉、北京）；境外三个为美国、日本、德国。位置是平台标注，未独立物理定位。TCP 使用目标 IP，不依赖 DNS/SNI/UUID；发起测量 API 的网络路径不等于各探针的路径。

| 测试 | 大陆六探针 | 境外三探针 |
| --- | --- | --- |
| A TCP 443，代理入口 | 0/18 | 9/9 |
| A TCP 8443，订阅 HTTPS | 0/18 | 9/9 |
| A 第三个管理 TCP 端口 | 0/18 | 9/9 |
| A ICMP | 18/18 | 9/9 |
| B TCP 443 | 18/18 | 9/9 |

A 三个 TCP 端口合计大陆 **0/54**、境外 **27/27**。此前本机/VPS双向报文显示 SYN 到达 A，A 发出并重传 SYN-ACK，本机未完成握手；相同 A 节点参数经 B 中转可完成 REALITY 与 HTTP 请求。

结论：已观察到跨大陆三网的 TCP 受阻与境外可达，高度符合 GFW 的 IP/TCP 过滤特征。**设备归属是强推断，不是直接证明**：服务商针对中国方向的云层/上游过滤未排除。不能从三个端口推定全部端口或 UDP 也被封，不能确定开始时间、触发原因或由哪次代理使用引起。

这一握手阶段故障无需 DNS/SNI/UUID 即可复现；修客户端 DNS、换 TLS 指纹、改 UUID、重装核心没有证据能恢复它。云层显示允许端口也不是完整路径证明。方法见[网络过滤与传输选型](../filtering-and-transports.md)。

## 节点 A 的 HTTP 与 DNS

观察窗口：2026-11-16 21:02–21:12，America/Los_Angeles（UTC 2026-11-17 05:02–05:12）。正式客户端始终为 B、rule 模式、TUN 开启。

临时核心来自 TLS 验证通过的 A 最终订阅；关闭自己的 TUN，仅 loopback 监听，拨号经正式 B。实际链路为“本机 → B → A → 测试站”。它只提供本次 TCP/独立 DNS 检查，不代表大陆直连 A，也不代表 A 的浏览器 UDP/WebRTC。

| 项目 | 观察结果 | 边界 |
| --- | --- | --- |
| HTTP/HTTPS出口 | trace 返回 A，204 小请求成功 | 证明本次中转后的最终出口 |
| Net.Coffee指定IP页 | 92/100，美国洛杉矶，Hosting/机房，AI 8/10 | 数据库判断，不是环境全测 |
| Net.Coffee信誉API | trust_score 92；响应 IP 为同 /24 另一地址（脱敏示例 `203.0.113.37`），CIDR为该 /24 | 查询与返回地址粒度不一致，不能称精确主机结论 |
| Vercel `/api/ip` | 返回 A，100/100、Residential；Proxy/VPN/Datacenter未知 | 与机房标签矛盾；不证明 VPS 是住宅网络 |
| Vercel `/api/check?format=json` | 2/100，`estimate:true`，coverage 62/100；字体/WebRTC/Intl未测 | 不可当作浏览器完整风险分 |
| 独立DNS | 两个全新域名均解析成功，权威端观察美国洛杉矶 Cloudflare 解析器 | 本次未观察到中国解析器，不覆盖所有应用DNS |
| ping0 | Turnstile验证页 | 未得分、未绕过 |
| A浏览器完整DNS/WebRTC | 未完成 | 正式路由未切换、临时通道未验证UDP |

A 订阅的 `tcp://127.0.0.1:5353#PROXY` 经节点访问服务器回环 DNS，而非客户端本机5353。临时核心使用该设置取得上表 DNS 结果。即使 `respect-rules:false`，明确的 `#PROXY` 也不能忽略；不能单凭该布尔值判为直连。

## 实际 Chrome 的结果

以下均属于正式 B 环境，不能归给 A：

| 检测 | 结果 |
| --- | --- |
| Net.Coffee `/claude/` | 100/100；三个出口栏均为 B；观察到境外 Google 解析器，页面显示DNS未泄漏；WebRTC空候选 |
| Net.Coffee `/webrtc/` | “已禁用或未暴露”，不能证明API真正禁用或所有STUN/TURN安全 |
| Vercel浏览器 | 32/100：语言13、中文字体14、Intl4、Emoji1；WebRTC项0 |
| fuck-claude.com浏览器 | 43/100：语言14、字体18、Intl9、Emoji2；该版本八项不包含WebRTC |

读取当时 `claude-page.js?v=20260916a` 发现：DNS无结果也给绿；WebRTC约5秒空结果也给绿；公网UDP判定排除IPv6及全部172.*，而非仅172.16/12。故“100/全绿”不构成严格验收，未证明本机已发生被漏检的泄漏。评分/字体与真实IP证据分开，详见[检测站边界](../detection-sites.md)。

## 配置问题与优先级

以下为当时读到的**实载状态**及待修建议，本案例没有执行修复：

| 项目 | 证据 | 后续价值 |
| --- | --- | --- |
| DNS悬空出口名 | nameserver/fallback 指向 `https://1.1.1.1/dns-query#<已失效的旧组名>`；运行核心没有该组 | 高：修实际维护源和覆写范围 |
| DNS可复现失败 | 核心API查询 `www.iana.org`、`example.com` 均HTTP500、`interface not found` | 已确认故障；网页可访问不等于核心DNS正常 |
| DNS来源 | `dns_config.yaml`保留旧名；B订阅开启DNS覆盖，A关闭 | 属B当前配置，不能解释A物理TCP故障 |
| TUN | enable/auto-route为true，strict-route为false | 评估strict-route与WSL/虚拟网卡/本机服务回归 |
| DNS劫持 | 仅`any:53`，缺`tcp://any:53` | 增补TCP53的候选；缺项不等于已捕获泄漏 |
| DNS模式 | Fake-IP；国内明确需求使用阿里/腾讯DoH；明文bootstrap为公共国内DNS | 保留Fake-IP；审查bootstrap，不新增CN兜底 |
| 物理网卡保护 | 39条出站Block，覆盖以太网/WLAN、全协议、各配置文件；UDP PROXY后有REJECT、尾部有MATCH REJECT | 有基础保护；本轮未故障注入，不能重申全面通过 |
| 新进程覆盖 | 新CodexPrimaryRuntime Node/PowerShell、UE Python真实路径缺对应保护；活进程GetPackageFamilyName返回15700 | 高：核对用途后补路径；父应用包规则不能推定覆盖无包身份子进程 |
| 包规则读取 | PackageFamilyName在规则本体，ApplicationFilter.Package可能为空 | 检查两处及实际进程，不凭WindowsApps目录判身份 |
| PROXY选择组 | select含节点和DIRECT | 建议保护组移除DIRECT；这不是“节点失败自动直连”的证据 |
| AI请求 | 进程规则、独立17890 CLI入口和环境变量已有；未知域名MATCH PROXY；未发现独立AI域名规则 | 可加靠前域名防覆盖，不能声称AI现在直连或穷尽第三方请求 |
| QUIC | Chrome/Edge UDP443拒绝，其他受保护程序UDP走代理 | 浏览器业务QUIC与Hysteria节点传输分开；不全封UDP破坏WebRTC |
| IPv6 | 核心/DNS ipv6:false；系统未全禁；当前无IPv6默认路由 | 未见当前公网IPv6出口；未来网络需重查，保留::1 |
| WebRTC | 注册表default_public_interface_only；本轮未再核对浏览器有效策略页 | 策略不强制代理；DNS修好后测国内外STUN、数字IP、TURN及恢复 |
| 同IP多协议 | A仅VLESS REALITY，无AnyTLS/Hysteria2/fallback | 先解决路径；TCP协议共用TCP故障，UDP尚待测 |

DNS行为的版本依据：[Mihomo v1.19.33 dns_dialer.go](https://github.com/MetaCubeX/mihomo/blob/v1.19.33/tunnel/dns_dialer.go#L70-L77)，找不到代理名时尝试绑定同名接口。处理流程见[DNS修复](../dns-repair.md)。

建议顺序：先修DNS维护源 → 补实际CLI/MCP运行时覆盖并移除保护组DIRECT → 单独评估strict-route/TCP53/AI域名规则 → 按后续授权开展节点失效、核心退出、TUN关闭、IPv6/网卡变化、STUN/TURN及恢复验证。每项单独回归，不以刷分代替证据。

## 未验证项与收尾

- 未对A做大陆直连的完整浏览器DNS/WebRTC验收；未测A UDP；未执行真实Claude/Claude Code账号会话。
- 此轮未停正式核心、断网、关闭TUN或注入故障。覆盖缺口是配置发现，不是已捕获公网旁路。WSL、虚拟机、所有网卡和全部子进程未逐一故障验证。
- 保留国内白名单仍有第三方请求暴露国内出口的条件性风险；不承诺任意国外网页绝无机会关联。整浏览器强制代理已被用户取消。
- 临时测试核心已停止，测试端口释放；正式核心、节点选择、rule/TUN状态保留；正式生成配置与profiles文件前后哈希一致。
- 详细原始证据留在原任务受限目录，未复制进技能；公共测量ID也未写入本案例，以免暴露部署地址。
- 后续研究见[2026-11-16技术快照](../research/2026-11-16-transports.md)。它是方案评估，不是这些问题已修复的记录。
