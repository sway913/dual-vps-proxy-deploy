# dual-vps-proxy-deploy

用于在两台全新 VPS 上部署八节点双机代理的 Codex Skill。近端 VPS 提供低延迟入口，远端 VPS 提供出口 IP；同时保留两台机器的直连节点和美国备用协议。

## 最终节点

| 节点 | 入口端口 | 出口 |
|---|---:|---|
| 🇭🇰 香港 RAW | 香港 `443/TCP` | 香港 IP |
| 🇭🇰 香港 XHTTP | 香港 `2053/TCP` | 香港 IP |
| 🇺🇸 美国 RAW | 美国 `443/TCP` | 美国 IP |
| 🇺🇸 美国 XHTTP | 美国 `8443/TCP` | 美国 IP |
| 🇭🇰→🇺🇸 美国经香港 RAW | 香港 `443/TCP` | 美国 IP |
| 🇭🇰→🇺🇸 美国经香港 XHTTP | 香港 `2053/TCP` | 美国 IP |
| 🇺🇸 美国 Hysteria2 备用 | 美国 `443/UDP` | 美国 IP |
| 🇺🇸 美国 AnyTLS 备用 | 美国 `2096/TCP` | 美国 IP |

香港到美国的机间链路使用独立的 VLESS Encryption + Reality + RAW/TCP Vision，监听美国 `36020/TCP`，仅允许香港服务器 IP 访问。

## 主要能力

- 自动检查两台新机器的系统、资源、端口、服务和防火墙工具。
- 自动生成全新的代理凭据与随机订阅路径。
- 自动发现 Reality 候选，并通过外部真实 RAW/XHTTP 连接筛选最终伪装目标。
- 部署 Xray RAW、XHTTP、中转以及 sing-box Hysteria2、AnyTLS。
- 在香港服务器发布 Clash 和全协议 Base64 两种订阅。
- 使用 Mihomo 校验订阅，并从外部逐节点验证出口 IP、TCP、UDP/DNS 和持续连接。

## Reality 目标规划

`scripts/plan_reality_targets.py` 必须在目标 VPS 本机运行。它会：

1. 使用入口或出口角色的种子候选；
2. 从成功证书的精确 SAN 自动扩展候选；
3. 对每个候选默认执行六轮带间隔的 TLS 1.3、证书、SNI 和 ALPN 检查，要求全部成功；
4. 查询 VPS 与目标 IP 的 ASN，但稳定性优先于同 ASN 和最低延迟；
5. 调用 `xray tls ping` 复核 REALITY 握手和后量子密钥交换；
6. 标记 Cloudflare ASN 与地区性教育/政府网络风险，输出临时候选。

规划器不会直接给出可发布的最终目标。必须从另一台 VPS 或用户网络使用真实 VLESS/Reality RAW 和 XHTTP 连续验收，并在至少五分钟后复测。可用 `scripts/verify_reality_e2e.py` 核对多个临时 SOCKS 入口的实际出口 IP。

示例：

```bash
python3 scripts/plan_reality_targets.py ingress --xray /usr/local/bin/xray
python3 scripts/plan_reality_targets.py exit --xray /usr/local/bin/xray
```

追加候选：

```bash
python3 scripts/plan_reality_targets.py ingress \
  --candidate example.edu.hk \
  --candidate-file ./my-candidates.txt
```

机器读取模式：

```bash
python3 scripts/plan_reality_targets.py exit --json
```

脚本只做 DNS、TLS 和公开 ASN 查询，不修改服务器配置。

运行依赖：Python 3.9 或更高版本及系统 `ca-certificates`；传入 Xray 路径后会额外执行官方 `xray tls ping` 检查。脚本应在目标 Linux VPS 本机运行，不能用管理电脑的网络结果代替。

## 安装 Skill

```bash
git clone git@github.com:sway913/dual-vps-proxy-deploy.git \
  ~/.codex/skills/dual-vps-proxy-deploy
```

已有目录时：

```bash
git -C ~/.codex/skills/dual-vps-proxy-deploy pull --ff-only
```

## 使用

在 Codex 中调用：

```text
使用 $dual-vps-proxy-deploy，在这两台全新 VPS 上部署最终八节点代理：
入口机：<IP>
出口机：<IP>
```

只读预检：

```bash
scripts/preflight.sh <入口机IP> <出口机IP> root
```

详细规格和部署顺序分别见：

- [`references/specification.md`](references/specification.md)
- [`references/runbook.md`](references/runbook.md)

## 订阅输出

默认在入口机发布：

```text
http://<入口机IP>:36010/<随机令牌>/clash.yaml
http://<入口机IP>:36010/<随机令牌>/all.txt
```

`clash.yaml` 和 `all.txt` 都包含八个节点；`all.txt` 是六个 VLESS、一个 Hysteria2、一个 AnyTLS 分享 URI 的整体 Base64。

## 安全边界

- 仅用于两台全新、未承载其他业务的服务器。
- 不在仓库、订阅或对话中保存服务端私钥和 SSH 密码。
- 美国机间端口只允许香港服务器公网 IP。
- Reality 目标必须在每台新服务器本机重新实测，不能机械复用历史域名。
- DNS、curl、证书或 `xray tls ping` 成功只代表候选资格；未通过真实 RAW/XHTTP 外部验收不得发布。
- 服务端配置通过原生校验后才启用服务。

## 官方参考

- [Xray-core](https://github.com/XTLS/Xray-core)
- [Xray REALITY 配置](https://xtls.github.io/config/transports/reality.html)
- [Xray 传输层配置](https://xtls.github.io/config/transport.html)
- [sing-box](https://sing-box.sagernet.org/)
- [RIPEstat Data API](https://stat.ripe.net/docs/data_api)
