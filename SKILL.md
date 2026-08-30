---
name: dual-vps-proxy-deploy
description: 在两台全新且未承载其他业务的 VPS 上部署经过验证的八节点 Xray 与 sing-box 双机代理：近端服务器负责低延迟入口，远端服务器负责目标出口 IP，包含直连、中转、Clash 与 Base64 统一订阅、Reality 伪装目标自动规划和端到端验收。适用于全新双机部署，不适用于单机代理或通用 VPN 管理。
---

# 双机代理部署

在两台全新服务器上直接部署最终八节点架构。

## 必读资料

- 规划或部署节点前，完整阅读 [references/specification.md](references/specification.md)。
- 选择、验收或更换 Reality 目标前，完整阅读 [references/reality-target-lifecycle.md](references/reality-target-lifecycle.md)。
- 对服务器执行任何写入或验收前，再完整阅读 [references/runbook.md](references/runbook.md)。
- SSH 可用时，先执行 `scripts/preflight.sh <入口机> <出口机> [SSH用户]`，以只读方式检查两台机器。
- 安装 Xray 后、生成正式配置前，分别在两台服务器本机执行 `scripts/plan_reality_targets.py ingress` 与 `scripts/plan_reality_targets.py exit`。排名第一的结果只是候选，必须通过外部真实 Reality 端到端测试后才能采用。

## 执行规则

1. 明确入口机、出口机、SSH 权限、系统版本、端口占用和防火墙管理方式。确认两台机器没有既有代理或其他业务；否则停止，因为不满足全新机器前提。
2. Xray、sing-box、Mihomo、XHTTP 与 VLESS Encryption 会持续演进。生成配置前必须核对官方最新文档、版本和客户端兼容性，不能直接套用过时字段。
3. Reality 目标必须由目标服务器本机规划，再从另一台 VPS 或用户网络使用真实 VLESS/Reality 客户端验收。DNS、curl、证书检查、`xray tls ping` 或历史可用记录都不能单独证明目标可用；地区性教育/政府站点不得自动采用。
4. 每次部署重新生成 UUID、Reality 密钥、Short ID、XHTTP 路径、VLESS Encryption 参数、协议密码、TLS 材料和订阅令牌。不得把私钥写入日志、仓库或对话。
5. 两台机器可在依赖允许时并行配置；每份配置先通过对应程序的原生校验，再启用 systemd 服务。
6. 只发布 `clash.yaml` 和 `all.txt` 两个订阅文件。
7. 必须从 VPS 网络之外逐节点测试。端口监听、服务器本机 curl 或 systemd 显示 active，都不能单独证明节点可用。
8. 真实端到端验收至少连续五轮，并在其他部署步骤完成后间隔复测。可使用 `scripts/verify_reality_e2e.py` 对多个本地 SOCKS 入口核对实际出口 IP；任何一轮失败都必须更换候选或查明原因，不能发布订阅。

## 完成标准

交付两个订阅地址、八个节点名称及其实测出口 IP、Reality 目标选择报告、程序版本、服务状态、监听端口和防火墙范围。只展示客户端需要的凭据，隐藏所有服务端私密材料。
