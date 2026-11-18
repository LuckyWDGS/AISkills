# 服务端部署与握手排障

## 选择与现场检查

优先沿用用户指定的服务栈。对于本技能所覆盖的自用场景，可采用管理面板 + 代理核心 + HTTPS 订阅反代；需要私有 DNS 才增加 AdGuard Home。3x-ui/Xray VLESS REALITY Vision 是已使用过的方案，不是强制唯一方案。

本用户要求先部署并测试所提供的 VPS，本机全面检查和修改按[独立阶段](local-review-and-approval.md)处理。3x-ui 是管理层，不自动增强协议抗过滤能力；无面板的 systemd 服务也是有效交付，不为比较方案额外安装公网面板。需要 HY2/AnyTLS/REALITY 共存时读取[多协议参考](multi-protocol.md)。

在安装/修改前检查：系统与架构、时钟同步、磁盘、现有服务与监听、宿主机防火墙、云安全组、现有 Web 服务和证书、客户端及服务端核心版本。下载使用官方发行源，核对可用的发布校验信息，记录实际版本。

大陆方向连接受阻或用户要求最新搭建方案时，先读[网络过滤与传输选型](filtering-and-transports.md)，区分TCP路径、协议握手与应用故障。多入口、固定出口、CDN和UDP备用按证据选择；日期版本与研究见[2026-11-16快照](research/2026-11-16-transports.md)。研究建议不自动授予部署权限。

**兼容性特别注意：** 2026-11-16 再次查阅的 Mihomo TLS 文档仍对 Xray v26.7.11+ 的 REALITY 兼容性有明确警告。以后执行时重读当时文档，不默认“双方最新”就兼容，也不因历史案例某组合可用而泛化。遇到问题，结合实际握手和发行说明选择经验证的组合；升级或协议迁移须符合当前任务范围。[Mihomo TLS](https://wiki.metacubex.one/config/proxies/tls/)

## 网络和管理入口

- 代理入口：在不抢占现有服务的前提下，TCP 443 是候选；检查运营商路径和客户端实测。若不可用，选其他明确放行的端口。不是所有服务器都必须改到 443。
- 订阅 HTTPS：与代理入口分开规划；8443 只是可用候选。两个普通服务不能同时直接监听同一地址的同一端口。
- SSH：保留当前可用入口。必须迁移时，先新增并验证另一个连接，再移除旧入口。
- 管理面板、原生订阅后端和私有 DNS 默认仅 loopback；通过授权 SSH 隧道管理。不部署公网开放递归 DNS。
- 云安全组与服务器防火墙分别检查入站/出站、协议、目标端口、源地址和优先级。TCP 规则不能被误配为 UDP；看到一条“允许”规则不代表实际方向正确。
- 只增删本任务需要的规则，不 flush 整套防火墙，不关闭所有安全策略排障。

## 创建/更新配置

1. 在受限远程目录备份相关配置、面板数据库和规则摘要。SQLite 使用一致性备份；不能对运行中的数据库文件随意覆盖。
2. 新建时生成独立 UUID、REALITY 密钥对、short ID 和高熵订阅 token。修复现有节点时尽量保留这些值及流量计数。
3. 已有面板时优先使用安装版本支持的 API，按本任务入站 ID/client 标识读取、合并和更新；不要用单节点模板覆盖其他入站。只有确有 API 缺口才考虑版本对应的数据库迁移，并处理锁、事务和服务重载。无面板时维护该服务的配置文件及单元，不引入无关数据库步骤。
4. 核对 VLESS UUID、端口、传输、Vision flow、SNI、REALITY 公钥与私钥配对、short ID、客户端指纹。对空 short ID 是否允许以服务端配置为准，不自作规定。
5. 私有 DNS 如果启用，监听 loopback，验证代理服务进程到 DNS 的可达性、上游 TLS 以及客户端实际解析路径。仅安装 AdGuard Home 不代表客户端正在使用它。
6. 运行所用核心的配置检查，成功后仅重载相关服务。检查 `systemctl`、实际监听和错误日志，再确认数据库/面板配置已反映在运行时。服务 active 不等于节点可用。

[3x-ui 官方项目及发行版](https://github.com/MHSanaei/3x-ui)、[官方 API 文档](https://github.com/MHSanaei/3x-ui/blob/main/docs/content/docs/en/reference/api/inbounds.mdx)、[AdGuard Home 文档](https://github.com/AdguardTeam/AdGuardHome/wiki/Configuration)。部署时读取与安装版本匹配的文档或源代码；不要把 main 分支的新 API 套到旧版本。

## 低权限服务与续期联动

- 以专用低权限身份运行；配置、密钥、证书目录与父目录权限都要允许所需读取，普通用户不能写。低端口按实际需要授予绑定能力，不为读取证书把整个服务改回 root。
- systemd 加固与核心能力一起验证。历史 sing-box 1.14.4 在 `RestrictAddressFamilies` 缺 `AF_NETLINK` 时启动失败，补上所需地址族后恢复；新环境先查日志和版本需求，不直接关闭全部沙箱选项或照抄地址族白名单。
- 配置检查、实际启动、稳定运行窗口分开记录。检查服务 PID、退出状态和重启计数的增量；修复前累计 `NRestarts` 非零不能冒充当前仍在重启，也不要清零来掩盖启动失败。
- 证书新增消费者时同步调整安装权限和续期 hook，覆盖实际使用它的 HTTPS、HY2、AnyTLS 服务。验证安装/重载方式及权限，但未来真实续期未发生时仍标未实测。细节见[订阅维护](subscription.md)。

参考 [sing-box v1.14.4](https://github.com/SagerNet/sing-box/releases/tag/v1.14.4)、[AnyTLS 入站](https://sing-box.sagernet.org/configuration/inbound/anytls/)、[TLS/REALITY](https://sing-box.sagernet.org/configuration/shared/tls/)。版本号只记录案例，部署时重新核对官方发行资产与校验。

## REALITY target 的选择

核查候选 target 的 TLS 能力、SNI 与证书域名关系、从服务器的访问性以及从用户网络建立 REALITY 的表现。官方候选条件和字段随版本核对：[XTLS REALITY](https://xtls.github.io/config/transports/reality.html)。

从 VPS 能访问 target 只说明服务端到目标的一段链路；必须再用客户端经物理网卡直连 VPS 测完整握手。排障一次只改变一个关键变量，如 target/SNI 或入口端口，并更新服务端、订阅和测试端相应参数。

历史案例：某用户网络下 Google target 直连握手失败，更换 Nvidia target 后恢复；同一环境的高位端口间歇失败，443 连续请求表现更好。这是排查思路，**不要把这些品牌域名或端口当成任何网络都适用的固定答案**。

如果比较端口要临时增加转发/监听，记录准确规则和撤销命令；测试完成删除该条临时规则，验证最终服务确实原生监听选定端口。

## 管理信息与秘密

密码、私钥、UUID、订阅 token、完整订阅 URL 只在受限任务文件中保存；不要进入技能、通用日志、截图、Git 或交接正文。Linux 文件通常用 0600/目录 0700；Windows 使用当前用户与 SYSTEM 的受限 ACL，单独 `chmod` 不能代替 ACL。

恢复访问时不要放宽全部 ACL 或打印秘密来证明读取成功。报告只给文件路径、检查是否通过和非秘密参数。
