# 协议、BBR 与订阅终验

先从本次工单和正在运行的配置确定目标 VPS、订阅、保留的协议、监听端口和预期出口。“检查是否开启／关闭”执行只读核验。“开启 BBR”或“关闭 REALITY”只对用户指定的目标实施。其他独立订阅各自按其协议选择验收。

## “最新”要核对哪一层

| 层级 | 取证方式 |
|---|---|
| 运行软件 | 在服务端用 systemd 的 `MainPID` 定位 `/proc/<PID>/exe`，读取该核心的版本。在本机从活动控制器的 `GET /version` 读取 Mihomo 版本，从运行中的 Clash Verge 可执行文件读取应用版本。逐项记录“运行版本、核验时的官方最新稳定版、核验时间及时区”。查询失败就记录缺项，发现差异时报告版本差距，升级按用户要求处理。[sing-box](https://github.com/SagerNet/sing-box/releases/latest) · [Mihomo](https://github.com/MetaCubeX/mihomo/releases/latest) · [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev/releases/latest) |
| 外层 TLS | 连接最终订阅给出的 **AnyTLS 服务端口**，验证证书链和节点配置中的域名或 IP SAN，读取该次连接实际协商的 TLS 版本。若要求强制 TLS 1.3，再检查服务端最低版本，并从同一测点限定 TLS 1.2 握手一次。分别记录明确的协议版本拒绝、EOF 或超时。 |
| AnyTLS 会话 | 查阅当时官方稳定发行标签下的协议规范。以 v2 为例，使用最终订阅的节点凭据，在已验证的 TLS 连接中认证，发送含 `v=2` 的 `cmdSettings`，读取服务端 `cmdServerSettings` 中的 `v`，再发送 `cmdHeartRequest` 并核对 `cmdHeartResponse`。记录服务端回报的版本和心跳结果。独立探针的握手与正式 Mihomo 走该节点的出口测试分别标明。若只测到了 TLS，就把 AnyTLS 会话版本列为未验证。[AnyTLS 稳定发行版](https://github.com/anytls/anytls-go/releases/latest) · [v2 协议说明](https://github.com/anytls/anytls-go/blob/v0.0.13/docs/protocol.md) |

## 核实 BBR 在代理连接上生效

同时核对内核运行值 `sysctl -n net.ipv4.tcp_congestion_control`、有效的开机配置，以及该代理的一条**新建且仍在传输或保持连接的 TCP 会话**。在该 VPS 上按代理进程和实际本地入站端口过滤 `ss -tinpe state established`，用连接四元组或前后快照中的新 socket inode 关联本次测试。TCP 详情中的算法是独立字段 `bbr`，前面可能还有 `sack`。无法对应到测试连接时，仅报告已经核实的内核值和持久配置。内核已启用且持久化正确时无需重新设置队列或重启 VPS。[BBR 配置与性能对比](performance.md)

## 关闭指定 VPS 的 REALITY

1. 找到提供 REALITY 的入站及其配置来源。获准变更后备份相关配置、订阅正文和元数据，只移除目标入站、发布节点及组内对它的引用。保留所选 AnyTLS 的证书、凭据和分流。先用对应核心校验候选配置，再重载对应服务。若服务仅支持重启，备好独立回滚路径，重连后先查生效状态。
2. 对专用旧端口，在服务器用 `ss -lntp` 确认监听已消失。从独立外部测点连接旧端口，再从同一测点验证保留的端口和协议。记录连接次数及拒绝或超时。单独一次超时只能说明该测点此次未能建连。共用端口时，核对分流或入站已移除，用旧 REALITY 参数验证握手失败，并在同一端口验证保留协议成功。
3. 从原私有 HTTPS 地址重新下载订阅并解析节点和组。若目标是只保留 AnyTLS，检查线上正文、交付的离线 YAML、正式 Clash 的该订阅缓存，以及活动控制器的节点、组成员和当前选择。若有配置覆写，按实际生效字段比较。保留原订阅地址，复核已有的流量和到期响应头。正式客户端的刷新按本次已有授权执行。[订阅与维护](subscription.md)

## 正式入口与出口

从运行配置发现普通代理监听和已有的 AI／CLI 专用监听。对每个入口分别显式访问 Cloudflare trace 和 ipify，逐项校验响应中的 IP 等于该订阅的预期出口。有两个入口时记录四次回显，只有普通入口时记录两次。可复用 `audit_exit_ip.py` 的 `confirmed_exit(session, expected)`，为每个监听建立独立会话并显式指定回环代理。另从活动控制器核实所选节点和国内白名单的 `DIRECT` 规则。保护国内来源时，在报告中遮盖意外回显地址。[出口查询脚本](../scripts/audit_exit_ip.py) · [线路与出口核验](route-and-ip-quality.md)

**脱敏实测示例。** 2026-11-18 19:54（洛杉矶时间），纽约订阅只保留 TCP 443 上的 AnyTLS。诊断连接协商 TLS 1.3，服务端回报 AnyTLS v2 并响应心跳，新建的 443 连接使用 BBR。纽约原 REALITY 端口 9443 无监听，洛杉矶测点两次连接均被拒绝，同一测点可连 443。运行中的 sing-box 1.14.4、Mihomo 1.19.34、Clash Verge 2.5.10 与当日官方稳定版一致。普通和 AI 专用入口的四次回显均为预期纽约出口，国内白名单命中 DIRECT。洛杉矶的独立订阅保留 AnyTLS 与 REALITY。后续核验重新读取当次版本、端口和预期协议集合。
