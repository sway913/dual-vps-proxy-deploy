# 最终架构规格

本规格仅用于两台全新且未承载其他业务的服务器。入口区域和出口区域可替换，但节点角色、协议组合和验收逻辑保持不变。默认端口被占用时才调整，并同步修改服务端、客户端、订阅、防火墙与测试记录。

## 部署输入

优先通过只读检查获取信息，只向用户询问无法发现的内容：

- 入口机 IP 与 SSH 权限；
- 出口机 IP 与 SSH 权限；
- 操作系统、CPU 架构、公网地址族、磁盘与内存；
- 防火墙管理方式及端口占用；
- 节点显示地区名称；
- 使用入口 IP 的 HTTP 订阅，或用户明确要求的 HTTPS 域名订阅；
- 客户端对 XHTTP、VLESS Encryption、Hysteria2、AnyTLS 和 Mihomo 配置格式的支持情况。

若只能密码登录且用户已授权使用密码，先安装用户公钥，并在独立 SSH 会话中确认密钥登录成功。不得保存或复述 SSH 密码。

## 八节点矩阵

| 节点名称 | 对外监听 | 最终出口 | 实现 |
|---|---:|---|---|
| `🇭🇰 香港 RAW` | 入口机 `443/TCP` | 入口机 | VLESS + Reality + RAW/TCP + Vision |
| `🇭🇰 香港 XHTTP` | 入口机 `2053/TCP` | 入口机 | VLESS Encryption + Reality + XHTTP |
| `🇺🇸 美国 RAW` | 出口机 `443/TCP` | 出口机 | VLESS + Reality + RAW/TCP + Vision |
| `🇺🇸 美国 XHTTP` | 出口机 `8443/TCP` | 出口机 | VLESS Encryption + Reality + XHTTP |
| `🇭🇰→🇺🇸 美国经香港 RAW` | 入口机 `443/TCP` | 出口机 | 独立入口用户经机间 VLESS 出站 |
| `🇭🇰→🇺🇸 美国经香港 XHTTP` | 入口机 `2053/TCP` | 出口机 | 独立入口用户经同一机间 VLESS 出站 |
| `🇺🇸 美国 Hysteria2 备用` | 出口机 `443/UDP` | 出口机 | sing-box Hysteria2 |
| `🇺🇸 美国 AnyTLS 备用` | 出口机 `2096/TCP` | 出口机 | sing-box AnyTLS |

同一数字端口的 TCP 与 UDP 可以共存。入口机 RAW 入站用独立 UUID/email 区分香港直出和美国中转，XHTTP 入站同理；路由规则只把两个中转身份送往机间出站。

## 机间传输

入口机到出口机固定使用独立的 Xray VLESS Encryption + Reality + RAW/TCP + Vision：

- 出口机监听 `36020/TCP`；
- 使用与六个公共 VLESS 节点完全独立的身份、Reality 密钥和 Short ID；
- 出口机运行独立的 `xray-transit.service`；
- 防火墙仅允许入口机公网 IPv4 访问 `36020/TCP`；
- 不修改任一服务器的默认路由。

## Reality 目标自动规划

目标选择必须在对应 VPS 本机进行。使用 [官方 REALITY 配置文档](https://xtls.github.io/config/transports/reality.html) 约束自动规划：

1. 从入口或出口角色的种子候选开始，并从成功证书的精确 SAN 中扩展候选。
2. 每个候选至少执行三次 TLS 1.3 握手；证书链、主机名和 SNI 必须通过系统 CA 校验。
3. 记录 ALPN、握手成功率、中位延迟、解析 IPv4 和目标 ASN。
4. 若 Xray 已安装，调用 `xray tls ping` 复核带 SNI 的握手、TLS 1.3 和 X25519MLKEM768 支持情况。
5. 与 VPS 同 ASN 的合格目标优先；其次选择低延迟、稳定且不属于风险 CDN ASN 的目标。
6. Cloudflare ASN 目标标记为风险项，不自动采用，避免未认证 REALITY 流量把服务器变成 CDN 转发入口。
7. `serverNames` 只写入已逐个完成 SNI 和证书验证的域名，不直接把证书中的所有 SAN 批量加入配置。

运行方式：

```bash
python3 scripts/plan_reality_targets.py ingress
python3 scripts/plan_reality_targets.py exit
```

脚本输出排序表、自动选择结果及 JSON 模式。若没有可自动采用的候选，停止配置并补充候选域名；不能静默退回固定目标。

## 服务划分

- 入口机：一个 Xray 公共/中转服务，外加 `proxy-subscription.service`。
- 出口机：`xray-public.service`、`xray-transit.service`、`sing-box-public.service`。

## 凭据要求

- 写入凭据前设置 `umask 077`，配置和凭据清单权限为 `0600`。
- 每个逻辑客户端使用唯一 UUID/email。
- 每次部署重新生成 Reality X25519 密钥、Short ID、XHTTP 路径、协议密码、TLS 私钥和至少 32 字节随机订阅路径令牌。
- 使用当前 Xray 版本支持的命令生成 VLESS Encryption 参数，并确认服务端与客户端完全一致。
- XHTTP 默认不启用额外 XMUX/reuse 设置，除非当前官方文档和客户端实测明确需要。

## 防火墙范围

保留 SSH 管理端口，新增规则限定为：

- 入口机：`443/TCP`、`2053/TCP`、`36010/TCP`；
- 出口机：`443/TCP`、`443/UDP`、`8443/TCP`、`2096/TCP`；
- 出口机 `36020/TCP`：仅允许入口机公网 IPv4，其他来源拒绝。

必须修改系统实际采用的持久化防火墙配置，并核对运行时规则。不得用宽泛端口段代替精确规则。

## 订阅规格

默认在入口机通过随机路径提供：

```text
http://<入口机IP>:36010/<随机令牌>/clash.yaml
http://<入口机IP>:36010/<随机令牌>/all.txt
```

- `clash.yaml` 包含全部八个节点。
- `all.txt` 是八行分享 URI 的整体 Base64：六行 `vless://`、一行 `hysteria2://`、一行 `anytls://`。
- 默认选择 `🇭🇰 香港 RAW`。
- 局域网、私有地址和中国大陆目标直连，其余流量使用当前选择节点。
- 自动测速组只包含三个 RAW 节点：香港 RAW、美国 RAW、美国经香港 RAW。
- XHTTP、Hysteria2 与 AnyTLS 作为手动备用。
- 订阅目录不得暴露列表、服务端配置、生成器源码、凭据清单或私钥。
