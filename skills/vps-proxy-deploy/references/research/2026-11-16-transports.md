# 2026-11-16 VPS传输与网络过滤技术研究

核查日：2026-11-16，America/Los_Angeles；资料抓取跨至UTC 2026-11-17凌晨。来源为官方发行API、版本源码、协议文档、研究者全文和学术出版页。本轮只读研究与技能编辑，未安装软件、升级核心、修改正式VPS/客户端、切换节点或执行故障注入。

**建议：先修已确认的DNS/出口保护问题，再评估不同入口到固定境外出口的容灾；新入口优先评估VLESS XHTTP + 正常TLS + 适配CDN/反代，Hysteria2作为经UDP实测后的候选。** 协议混淆、入口冗余与fail-closed分别解决识别、可用性和旁路风险，没有“永久不封”的证明。

目录：

- [当前证据与选型前提](#当前证据与选型前提)
- [正式版本快照](#正式版本快照)
- [可部署方案比较](#可部署方案比较)
- [最新独立研究](#最新独立研究)
- [适合本案例的后续方案](#适合本案例的后续方案)
- [复核来源](#复核来源)

## 当前证据与选型前提

[脱敏案例](../cases/2026-11-16-network-audit.md)中，目标VPS A的三个TCP端口大陆0/54、境外27/27；ICMP可通，对照VPS B的大陆TCP可通；A经B中转可完成REALITY。故当前主要障碍在大陆方向TCP路径，不能用换DNS、SNI、UUID或同IP AnyTLS的承诺替代链路证据。UDP尚未验证，拦截设备归属仍有服务商/上游策略未排除。

当时本机Mihomo 1.19.33、A服务端Xray26.9.30。以下“源码/文档支持”不表示已部署或实测这些新方案。已在其他路径观察到的网页评分，也不是抗封锁证据。

## 正式版本快照

各项目GitHub `releases/latest` 在查询时返回如下版本，均 `prerelease:false`、`draft:false`。这不是自动升级建议；未来执行须重查。

| 项目 | 版本 | 发布日，UTC | 本轮核实的要点 |
| --- | --- | --- | --- |
| [Xray-core](https://github.com/XTLS/Xray-core/releases/tag/v26.11.9) | v26.11.9 | 2026-11-09 | XDRIVE公开测试与优化；Chrome155+指纹的“尚未被针对”描述明确指俄罗斯TSPU |
| [Mihomo](https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.34) | v1.19.34 | 2026-11-11 | TUN auto-route、CONNECT响应数据等修复；发行记录不证明能解除大陆IP/TCP阻断 |
| [sing-box](https://github.com/SagerNet/sing-box/releases/tag/v1.14.4) | v1.14.4 | 2026-10-24 | 发行页仅列修复改进；具体协议能力按文档/源码核验 |
| [Hysteria2](https://github.com/HyNetworks/hysteria/releases/tag/app/v2.14.0) | app/v2.14.0 | 2026-11-15 | ACL expr引擎、UDP转发性能、quic-go0.65.0；不等于新防封保证 |
| [AnyTLS-go](https://github.com/anytls/anytls-go/releases/tag/v0.0.13) | v0.0.13 | 2026-06-27 | 增加禁用连接复用的选择；作者未发现优化良好组合的复用有问题，不应默认关复用 |
| [NaiveProxy](https://github.com/klzgrad/naiveproxy/releases/tag/v154.0.8037.49-5) | v154.0.8037.49-5 | 2026-10-22 | 发行方撤销受影响eMudhra中间证书并提出安全更新要求；与国内路径是否被封分开处理 |

Hysteria旧项目入口 `apernet/hysteria` 当前重定向到官方 `HyNetworks/hysteria`。发行来源与二进制校验信息应随部署记录，不能通过名称相似的第三方脚本升级。

## 可部署方案比较

| 方案 | 本轮证据 | 与Windows/Mihomo的关系 | 局限和建议 |
| --- | --- | --- | --- |
| VLESS REALITY | 现有案例经中转可用；官方文档描述认证与伪装目标 | Mihomo原生支持，但有Xray兼容性警告 | 保留已验证组合；无法保证修复同IP TCP握手受阻 |
| VLESS XHTTP + 正常TLS | 官方设计支持HTTP不同上行模式、上下行分离、CDN/反代 | Mihomo文档和v1.19.33源码均已支持 | 值得作为新的HTTP入口候选；需域名/证书与边缘/回源实测 |
| Hysteria2 + Salamander/Gecko | 官方协议、变更日志及Mihomo v1.19.33源码 | 原生Gecko字段和处理已存在，非仅主分支计划 | 适合独立验证UDP路径；Gecko仍标实验性，不承诺不识别 |
| AnyTLS | 参考协议针对TLS嵌套、分包填充和复用；Mihomo/sing-box支持 | 可保留现客户端 | 同IP仍走TCP，不是当前TCP路径问题的优先解法 |
| NaiveProxy | Chromium网络栈、HTTP/2或HTTP/3 CONNECT、前置服务与padding | sing-box文档支持Windows，需libcronet.dll；本轮未找到Mihomo原生Naive支持依据 | 适合作为另栈候选，增加进程/防火墙/更新维护；不解除IP层阻断 |
| 不同网络入口 → 固定出口 | 架构推断；本案例已验证一条B→A的TCP路径 | 可由兼容客户端/服务端组成，具体链路待设计 | 对入口失效更有价值；固定出口仍是单点，UDP/DNS必须单独证明 |

### XHTTP需要核对的具体区别

[Xray设计说明](https://github.com/XTLS/Xray-core/discussions/4113)与[Mihomo传输文档](https://wiki.metacubex.one/config/proxies/transport/#xhttp-opts)均有XHTTP；[v1.19.33 VLESS源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.33/adapter/outbound/vless.go)含实际XHTTP分支。不能继续使用“Clash不支持XHTTP”的旧结论。

- Mihomo文档当前仅VLESS可选XHTTP，支持auto、stream-one、stream-up、packet-up；默认H2，H3/H1.1需匹配ALPN。优先验证H2，无需为了“新”强制全部QUIC。
- 文档明确Mihomo不填 `reuse-settings` 时不启用复用，与Xray默认值不同。配置可接受不代表吞吐、延迟与指纹完全相同；不要直接把Xray JSON粘进订阅。
- CDN流式上传能力、gRPC支持、POST大小、缓冲与超时决定可用模式。packet-up兼容范围较广是设计说明，不代表每家CDN都保证成功。
- **普通CDN入口用正常TLS，REALITY不能原样穿过普通CDN的TLS终止。** XHTTP本身也可搭REALITY直连，那是另一条路径。
- 如选Cloudflare，其[gRPC要求](https://developers.cloudflare.com/network/grpc-connections/)包含443、TLS、HTTP/2 ALPN、相应Content-Type和启用代理；文档也指出Access不为该gRPC反代流量提供认证保护。要独立保护代理/管理入口。回源按[Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)核对证书；这只是兼容性资料，不是对特定用途、价格或大陆可达性的保证。

### Hysteria2的新增能力

[官方Changelog](https://hysteria.network/docs/Changelog/)记载：2.9.2加入实验性Gecko，2.10.0加入ECH，2.11.0加入默认Chrome QUIC指纹拟态，2.12.0加入Mimic，2.12.3增加ECH生成命令，2.13.0更新Chrome154拟态，2.14.0更新ACL/性能。版本先后不等于每项都应开启。

- [Gecko协议](https://hysteria.network/docs/developers/Protocol/)在Salamander外增加对QUIC握手长头的分片与随机填充。Mihomo[文档](https://wiki.metacubex.one/config/proxies/hysteria2/)和[v1.19.33源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.33/adapter/outbound/hysteria2.go)已有Gecko密码及包长字段，也有ECH配置；本轮未做双方实际互通，未证实Mihomo继承上游所有Chrome拟态行为。
- [端口跳跃](https://hysteria.network/docs/advanced/Port-Hopping/)针对部分端口级UDP限制；官方明确整个UDP受限时无效。需要服务端端口/防火墙一致，不自动开放大段端口。
- [Mimic](https://hysteria.network/docs/advanced/Mimic/)在两端用eBPF改写包头，**仅Linux**、需单独组件与权限；不能直接加入本用户Windows客户端，也不能保证穿过已有TCP过滤。
- [ECH](https://hysteria.network/docs/advanced/ECH/)保护握手SNI，不能隐藏目的IP；官方认为已启用整体混淆时不再增加这层收益。密钥更新和客户端配置同步也是维护成本。
- [官方CDN说明](https://hysteria.network/docs/misc/CDN/)明确Hysteria认证后转为自定义协议，不能直接套普通HTTP CDN。它与XHTTP的CDN能力不是一回事。

### AnyTLS、Naive与REALITY兼容性

[AnyTLS README](https://github.com/anytls/anytls-go/blob/main/readme.md)将anytls-go定位为参考实现，并提醒示例默认TLS安全设置不足；[v0.0.13 FAQ](https://github.com/anytls/anytls-go/blob/v0.0.13/docs/faq.md)明确默认padding不能保证不被识别，也列出时序、下行、主动探测等边界。采用有正常证书验证的实现；不因“AnyTLS”名称就认为公网流量不可分类。

[Naive设计](https://github.com/klzgrad/naiveproxy)使用Chromium栈与HTTP CONNECT；[sing-box Naive文档](https://sing-box.sagernet.org/configuration/outbound/naive/)标注1.13.0起可用，当前Windows依赖匹配的libcronet.dll。该文档明确自签证书会改变流量特征，不建议生产使用。本轮没有安装外部客户端，若以后使用须把新增可执行文件纳入出口和故障保护。

2026-11-16复核的[Mihomo TLS文档](https://wiki.metacubex.one/config/proxies/tls/#reality-opts)仍警告不考虑Xray26.7.11+兼容性。这是互操作风险，不表示所有此后版本必定失败；本案例26.9.30经中转成功也不能反证警告无关。升级前隔离验证实际组合，不同时盲升两端。

### XDRIVE属于观察项

Xray26.11.9的[XDRIVE说明](https://github.com/XTLS/Xray-core/pull/7352)为Google Drive后端公开测试：两端同版本、近期可能breaking change、需Google账号/API密钥、VLESS Multiplex+Encryption；作者报告建立通道需数秒、随后RTT约1.5秒。

该说明主要讨论俄罗斯/伊朗与Google可达路径，Chrome155+“未被TSPU针对”不能外推中国。用户大陆网络到相关Google入口是否可达未验证，也没有当前Mihomo可直接替换使用的证据。暂不选为本案例主方案；作者性能报告不作为本用户实测或费用估算。

## 最新独立研究

区分研究者结果、作者设计宣称和本用户实测。以下不是正式节点新测试；同一方法在一个国家、时间、运营商成功，不能承诺以后在中国全网可用。

| 研究与时间 | 本轮读取范围 / 研究观察窗口 | 对当前任务的意义 |
| --- | --- | --- |
| [CircumVolve，CCS2026](https://gfw.report/publications/ccs26/en/)，页面发布及更新2026-11-16 | 读取研究者全文的方法、结果与限制；含中国/伊朗/巴基斯坦/哈萨克斯坦实网；中国实验绝对起止未核实 | 作者报告47种策略，其中34种对中国某些设置有效；这是发现引擎，不是面向终端用户的代理安装包 |
| [QUICstep，PoPETs2026 Issue1](https://petsymposium.org/popets/2026/popets-2026-0014.php) | 出版页摘要及固定commit的[复现说明](https://github.com/inspire-group/QUICstep-PETS/tree/fdc3ff5f1a39396bb0ba8dcb2015ec9df30a89aa)；本轮未核验完整测量日期 | 仅握手经加密通道、再利用QUIC迁移；对隐藏国内出口的目标不能直接套用 |
| [CensorLess，PoPETs2026 Issue3](https://petsymposium.org/popets/2026/popets-2026-0096.php) | 出版页摘要，未验证完整实网窗口或复现部署 | 云函数桥接、轮换、迁移有研究价值；云配额、认证、费用、固定出口与真实地区可达性需另证 |
| [QUIC SNI审查，USENIX Security2025](https://gfw.report/publications/usenixsecurity25/en/)，发布2025-07-31 | 全文方法与结果；报告2024-04-07起观察到机制，含2024-11/12和2025-01具体实验 | QUIC Initial可被解析并据SNI过滤；“用了QUIC”不等于不可识别。这些测量不证明2026目标A的原因 |
| [区域审查，S&P2025](https://gfw.report/publications/sp25/en/)，发布2025-05-11 | 全文摘要/方法；纵向2023-11至2025-03，2024-03至10有缺口 | 河南区域行为可不同于全国机制；支持跨地区、跨运营商对照，不能用单地成功概括大陆 |
| [443异常阻断观察](https://gfw.report/blog/gfw_unconditional_rst_20250820/en/)，事件2025-08-20 | 约北京时间00:34–01:48的74分钟观察 | 记录无条件443 RST，说明服务正常与端口常用不等于路径稳定；该事件特征不能套成本例三端口受阻的归因 |

CircumVolve明确主要供研究者发现策略，TLS/QUIC部分只评估初始包，未覆盖完整握手，也未评估私有/全加密协议；不能把“34种”理解为34套可直接保护此VPS的成熟方案。本轮没有运行其畸形包或DPI探测实验。

QUICstep公开说明只把Initial/Handshake走WireGuard等握手通道。若迁移后的数据直接从本机到目标站，目标就可能观察到本机国内公网源地址；这是对架构的判断，不是本用户泄漏实测。它解决某类SNI审查的思路与“始终固定境外出口”要求不同，不能为提速自动采用。

CensorLess摘要中的97%成本下降是作者对特定基线的结果，不作为本用户预算。桥轮换也不能自动保证最终出口固定。

GFW首页把两篇PoPETs研究列入2026年7月新闻，而出版页分别为Issue1和Issue3；不把新闻月份当作两篇的精确发表日。GFW对应两篇全文入口本轮返回403，后改读公开出版页/公开复现说明；没有绕过访问验证，也没有声称读完其全文。

## 适合本案例的后续方案

1. **先收紧本地可靠性。** 修B的失效DNS组名、核对CLI/MCP实际路径保护、移除保护组DIRECT；单独评估strict-route和TCP53。保持用户选定的国内白名单、可用WebRTC与loopback边界。详见[案例待修项](../cases/2026-11-16-network-audit.md#配置问题与优先级)。
2. **保留现有可用连接，验证新入口。** 候选A为“客户端→适配的CDN/XHTTP正常TLS→境外源站/固定出口”；候选B为“客户端→不同网络的独立入口→固定出口”。CDN源站可达、域名、证书和中转完整能力都尚待实测，不自动变更现有订阅。
3. **再测UDP备用。** 如目标A的UDP可达，独立验证Hysteria2/Gecko；客户端/服务端正常认证、业务UDP、DNS、WebRTC和失效拒绝直连需分别通过。A的ICMP成功不能预先判UDP成功。
4. **实现故障保护与有限切换。** 只有经验证的代理进入保护fallback，不能含DIRECT。健康检查覆盖真实链路、出口和所需能力，防止204能通而DNS或UDP坏掉；切换到不同入口仍验证最终出口。
5. **接受固定出口的单点边界。** 多入口仍共享固定出口主机/上游；若该出口本身故障，严格模式应失败并保留出口保护。是否另设可变出口灾备属于后续架构选择，不能默默切到国内直连。

本轮新技术均处于“资料核实/候选方案”状态，没有“抗封实测通过”的项目。正式部署以后需要按[网络过滤指引](../filtering-and-transports.md)、[验证](../validation.md)和[故障测试](../failure-testing.md)留下真实结果。

## 复核来源

优先复核顺序：准确发行tag/源码 → 当前官方协议和客户端文档 → 原始研究的方法与限制 → 当前用户的实际路径。本文各节已链接主要来源；额外入口：[Xray XHTTP文档](https://xtls.github.io/config/transports/xhttp.html)、[REALITY文档](https://xtls.github.io/config/transports/reality.html)、[Mihomo VLESS](https://wiki.metacubex.one/config/proxies/vless/)、[Mihomo AnyTLS](https://wiki.metacubex.one/config/proxies/anytls/)、[GFW Report研究索引](https://gfw.report/en/)。

带日期报告保留历史版本，不不断覆盖成“永远最新”。后续有新实测时另加日期记录，并把实际部署状态与本文的待评估建议区分。
