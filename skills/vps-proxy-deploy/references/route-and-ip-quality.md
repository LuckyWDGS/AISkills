# 线路实测与出口 IP 交叉核验

用户说“测一下这条路线”时，直接检查当前链路、做轻量线路实测，并调查实际出口的 IP 质量。用户只给一个待查 IP 时做指定地址查询。只问住宅属性或信誉时，省去吞吐测试。给出当次查询的时间、时区、来源和结果。以当前生效的客户端为准，对比其他可用路径时可用隔离客户端保留用户正在使用的连接。

## 先确定测的是哪条路

- 在本机读取正在服务的核心、代理端口、规则模式、TUN 和严格路由、活动策略组及其最终节点。看终点节点是否设置 `dialer-proxy`、前置组当前选了谁，以及对公网生效的 `DIRECT` 规则。结合核心在物理网卡上的连接判断实际第一跳。有自有落地机且已可访问时，用其服务端 socket 对端交叉验证中转。将入口、落地和网站所见出口分别记下。同一个出口 IP 可以对应直连和多种中转。
- 通过已核实的本地代理分别请求 Cloudflare trace 和 ipify。用户使用 TUN 时，再对相同地址族单独测一次无显式代理的系统请求。避免继承环境代理或把“无显式代理”直接解释成“已走物理直连”。隐私要求严格且路径存疑时，先经自有受控服务验证；不为取得对照而把国内公网地址暴露给外部回显站。记录结论时隐去意外来源地址。[Cloudflare trace](https://1.1.1.1/cdn-cgi/trace) · [ipify](https://www.ipify.org/) · [路径取证](validation.md)
- 用户关心泄漏时，在实际 DNS 监听查询 `whoami.cloudflare`（CH 类 TXT），用受控接收端或 `stun.cloudflare.com:3478` 比较普通 UDP 和经 SOCKS5 的来源。网页 IP、DNS 回显、STUN 和真实浏览器 WebRTC 各自说明所测流量。说明第一跳可以看到连接来源、落地看到上一跳、目标网站看到本次出口，命中公网直连规则的请求另算。[流量防泄漏](traffic-privacy.md)

## 交叉核对 IP 属性、信誉与运营商

逐家查同一个完整公网 IP。保留原字段和来源链接，标出运营商级、网段级和单个地址的证据。各家分值保留原量表，分别给出定位、信誉和家宽结论。日常检测与结果解释见[检测站与评分边界](detection-sites.md)。

| 渠道 | 重点取证 |
|---|---|
| [IPinfo](https://ipinfo.io/) | 打开 `https://ipinfo.io/{IP}` 的网页详情。记录位置、ASN 与 AS Type、Company、网段，以及 Anonymization 下的 VPN、Proxy、Tor、Relay、Hosting、Residential Proxy。基础 JSON 可能只提供位置和 ASN。 |
| [ip-api](https://ip-api.com/docs/api:json) | 查 `/json/{IP}`，显式请求 `query,isp,org,as,mobile,proxy,hosting` 等字段并核对 `query`。免费 JSON 接口使用 HTTP，只提交待查公网地址。 |
| [MaxMind 官方演示](https://www.maxmind.com/en/geoip-demo) | 在 `?ip_address={IP}` 的演示提交目标，读取 ISP、Organization、Network 与 Connection Type。把 `Cable/DSL` 等值作为连接类型原样引用；公开演示缺少的匿名代理字段记为未提供。用本地 GeoLite2 补充时写明库名、构建日期和可查字段。 |
| [IP2Location](https://www.ip2location.com/demo) | 看 `https://www.ip2location.com/{IP}` 完整页的 ISP、Usage Type、Category、Anonymous Proxy、Proxy Type、Fraud Score，必要时核对 `is_data_center`、`is_vpn`、`is_residential_proxy`。免费 JSON 的 `is_proxy=false` 与详细页的 `DCH` 可以同时成立。 |
| [IPPure](https://ippure.com/) | 当前出口用 `https://my.ippure.com/v1/info` 核对返回的 `ip`，读取 `isResidential`、`isBroadcast` 和 `fraudScore`。查指定 IP 时打开 `https://ippure.com/?ip={IP}`，在目标 IP 卡片读取原生/广播、住宅/机房、系数和分档。首页的 My IP 是另一张卡。人机比等数据要标注站点展示的范围。 |
| [CleanIP](https://cleanip.io/ip-risk-check) | 对同一目标读取纯净度分和等级、地址类型、风险命中与检测覆盖。[读取 CleanIP 报告](#cleanip-报告) |
| [RIPEstat](https://stat.ripe.net/docs/data-api/api-endpoints/network-info.html)、[RIR RDAP](https://www.arin.net/resources/registry/whois/rdap/)、[PeeringDB](https://www.peeringdb.com/) | 核对当前 BGP 公告前缀和全部起源 ASN、注册机构的分配范围和登记组织。用 `https://www.peeringdb.com/api/net?asn={ASN数字}` 和运营商官网确认其业务是骨干传输、托管、企业接入或零售宽带。分别报告 ASN 所有者、网段使用公司与实际服务形态。 |
| [Tor Project](https://check.torproject.org/)、Spamhaus DROP [IPv4](https://www.spamhaus.org/drop/drop_v4.json) / [IPv6](https://www.spamhaus.org/drop/drop_v6.json)、[AbuseIPDB](https://www.abuseipdb.com/) | Tor 的当前出口回显须与目标一致，指定地址另查官方出口列表。对 DROP 比对相应地址族的 CIDR 并记录名单时间，未命中只适用于该名单。需举报历史时再查 AbuseIPDB 的报告数及时间窗。遇到挑战、403、429 或付费字段，记录实际限制。 |

`AS Type=ISP` 描述整个自治系统，`Hosting not detected` 描述该产品本次的检出结果。若 MaxMind 报宽带连接、IPPure 报住宅，同时 IP2Location 报 `DCH/Web Hosting`，三项都呈现。可据证据判断“公开信誉较低风险、住宅标签有分歧、实际家庭接入未证实”。用户拥有一台 VPS 本身也无法证明上游最后一段是家庭宽带。仅有网段级数据时注明覆盖范围。

### CleanIP 报告

打开 `https://cleanip.io/{IP}/assessment`，或在风险检测页输入目标公网 IPv4 或 IPv6。查当前线路时填入已核实的出口。等报告加载完，再核对结果卡上的完整地址。静态 HTML 会显示「系统打分中… 0/100」。遇到验证页、限流、超时或地址不符时，将该项记为「未核验」并写明原因。

记录查询时间、报告链接、纯净度原分（0–100，越高越好）及等级（F 至 A+）。按页面实际展示记录住宅、机房或移动等地址类型、原生或广播标签，以及判定是否来自 ASN 推断。对代理与匿名、滥用与自动化、名单与蜜罐、举报与攻击四组信号，分别记录命中、有效未命中和待核验项。报告若给出历史记录、证据时间或邻居网段数据，保留其时间和范围。第三方欺诈分另列，分数方向按来源解释。[评分规则](https://cleanip.io/scoring) · [风险项说明](https://cleanip.io/risk-signals)

审查时将 CleanIP 与其他来源对照，保留互相冲突的标签。CleanIP 引用的 AbuseIPDB、Tor 等上游与单独查询重复时，只计作同一项证据。已有授权的 CleanIP MCP 也可使用 `check_ip`。匿名 MCP 仅提供归属地和 ASN，缺少评分时继续读取网页报告。[数据来源](https://cleanip.io/data-notes) · [官方 MCP 说明](https://cleanip.io/mcp)

## 运行查询脚本

[audit_exit_ip.py](../scripts/audit_exit_ip.py) 使用 Python、`requests` 和 `lxml`。从当前客户端发现端口，把下例中的 `$localProxy` 设为带端口的回环 HTTP 代理，将 `$expectedExit` 或 `$targetIp` 设为本次公网地址。工作目录为技能目录时可用以下命令，其他位置使用脚本的实际路径，结果写入本次任务的工作目录。

```powershell
py -3.12 scripts/audit_exit_ip.py --proxy $localProxy --current --expected-exit-ip $expectedExit --output $resultFile
py -3.12 scripts/audit_exit_ip.py --proxy $localProxy --ip $targetIp --output $resultFile
```

第一条在查库前后分别核对两个回显。尚不知道预期 IPv4 时可省略 `--expected-exit-ip`，提供预期 IPv6 时按 IPv6 复核。若 IPPure 或 Tor 对当前来源报出另一 IP，仅保留目标地址的查库结论，并调查分流。第二条只查指定地址，另需打开脚本给出的 IPPure 目标卡。两种模式都会给出 CleanIP 目标报告链接并标为 `lookup_target_card`。审查者打开报告，把实读结果或未核验原因写入最终审查，同时按查回的 ASN 核对运营商业务。

在出口已知的自有 VPS 上做指定地址查询，可将第二条的 `--proxy $localProxy` 换成 `--host-route`。该选项使用主机网络路由并忽略 HTTP 代理环境变量。国内电脑需要隐藏来源时选经过验证的本地代理。缺少 Python 依赖时，从已确认的查询路径使用表内的公开网站即可。

脚本也读取 Scamalytics 目标页的欺诈分、风险等级、代理标记及评分依据（`assessment`）。汇总时注明站方使用单个地址观测还是运营商估分。IPQualityScore 可提供第二份评分。浏览器侧按[检测站与评分边界](detection-sites.md)补测。

退出码 0 表示脚本所查来源均返回，1 表示有缺项或待查页面，2 表示当前出口未验证或参数错误。按单项的 `fields`、`missing_fields` 和 `reason` 补查。脚本只采集地址证据，物理第一跳、DNS、UDP 与性能按上文和下节单独实测。

## 测国内可达性、速度或对比中转

1. **可达性**。从用户实际线路测试目标业务端口和协议握手，记录成功次数、TCP 建连耗时及 HTTPS 首字节时间。要回答“国内三网”时，可用 Globalping 的中国大陆电信、联通、移动探针测试同一业务端口，记录测量链接、探针城市/ASN、次数、成功率和 RTT。某运营商无可用探针时标出缺口。需要查路径变化时再补 traceroute，注明方向；ICMP、TCP 握手与业务下载各自计量。[Globalping](https://globalping.io/) · [跨网可达性](filtering-and-transports.md)
2. **速度与流量**。比较直连和中转时固定出口、服务端协议、文件、方向和连接数，在相近时段交错做小样本。例如每条路径从自有落地机向国内发送 3 次 4 MiB 文件，核对字节数或摘要，报告中位数、范围和失败数。按需另测上传。Cloudflare 测速反映到该 CDN 的路径。用户问“VPS 访问国内”时，从 VPS 访问已核对国内实际对端的站点另测。在结果中写清谁发给谁、Mbps/MB/s 和测试流量。[性能测量](performance.md)
3. **交付**。先写当前实际路径和出口，再列各库原值、ISP 依据及分歧，最后给实际可达性和速度。保留来源链接、测量时间与未覆盖项。只查指定 IP 时只交对应结果。网段抽样时记录 CIDR、实际样本和有效样本数，共享数据源按它的配额查询。
