# 全新双机部署手册

先完整阅读最终架构规格。本手册只部署已经验证的最终八节点方案，并假定两台 VPS 均为全新机器。

## 1. 确认环境

1. 运行只读预检脚本。
2. 确认系统、架构、CPU、内存、磁盘、时钟、公网 IPv4、SSH 和防火墙管理方式。
3. 确认所需端口空闲，机器上没有既有代理、隧道、面板或其他业务；发现既有业务即停止。
4. 测试两台 VPS 之间的直接连通性。
5. 从官方来源确认 Xray-core、sing-box 和 Mihomo 当前版本与配置字段。
6. 确认目标客户端支持全部计划协议。

## 2. 安装核心并规划 Reality 目标

从官方发布源安装经过校验的 Xray：入口机和出口机都安装。出口机再安装经过校验的 sing-box。

在生成 Reality 配置前，把目标规划脚本放到服务器或通过 SSH 标准输入执行：

```bash
python3 plan_reality_targets.py ingress --xray /usr/local/bin/xray
python3 plan_reality_targets.py exit --xray /usr/local/bin/xray
```

- 第一条必须在入口机本机运行，第二条必须在出口机本机运行。
- 保存每台机器的 `SELECTED_TARGET` 和 `SERVER_NAME`。
- 若脚本未给出可自动采用结果，补充本地区域候选后重新运行。
- 入口机两个公共 Reality 入站使用入口机选择结果；出口机两个公共入站和机间入站使用出口机选择结果。

## 3. 生成部署凭据

设置 `umask 077`，生成：

- 六个公共 VLESS 身份；
- 一个独立机间 VLESS 身份；
- 各 Reality 入站的 X25519 密钥与 Short ID；
- XHTTP 路径及匹配的 VLESS Encryption 参数；
- Hysteria2、AnyTLS 凭据与 TLS 材料；
- 至少 32 字节随机订阅令牌。

建立权限为 `0600` 的节点、端口、身份、路由与分享 URI 对照表。服务端私钥不得进入订阅或对话。

## 4. 部署出口机

创建专用配置目录和三个 systemd 服务：

- `xray-public.service`：`443/TCP` 的 VLESS Reality RAW Vision，以及 `8443/TCP` 的 VLESS Encryption Reality XHTTP；
- `xray-transit.service`：`36020/TCP` 的机间 VLESS Encryption Reality RAW/TCP Vision；
- `sing-box-public.service`：`443/UDP` 的 Hysteria2 与 `2096/TCP` 的 AnyTLS。

先用已安装程序原生校验配置，再设置持久化防火墙：

- 公开允许 `443/TCP`、`443/UDP`、`8443/TCP`、`2096/TCP`；
- `36020/TCP` 仅允许入口机公网 IPv4；
- 保留 SSH。

启动并启用三个服务，检查 journal 和精确监听地址。从入口机验证机间连接的最终出口为出口机公网 IP。

## 5. 部署入口机

配置一个 Xray 服务：

- `443/TCP` RAW Reality Vision 入站，含香港直出和美国中转两个独立身份；
- `2053/TCP` VLESS Encryption Reality XHTTP 入站，含香港直出和美国中转两个独立身份；
- 本机 direct/freedom 出站；
- 指向出口机 `36020/TCP` 的专用 VLESS RAW/TCP 出站；
- 按用户 email 路由，仅将两个中转身份送往机间出站。

原生校验配置后，持久化允许 SSH、`443/TCP`、`2053/TCP`、`36010/TCP`，再启动并启用服务。

确认两个直出身份使用入口机 IP，两个中转身份使用出口机 IP；中转失败时不得静默回落为入口机直出。

## 6. 发布两个订阅

在入口机创建并启用最小化的 `proxy-subscription.service`，监听 `36010/TCP`，只发布：

```text
http://<入口机IP>:36010/<随机令牌>/clash.yaml
http://<入口机IP>:36010/<随机令牌>/all.txt
```

生成后执行以下校验：

1. `clash.yaml` 恰好包含八个唯一节点名，默认节点为香港 RAW。
2. 自动测速组恰好包含三个 RAW 节点。
3. 使用目标 Mihomo 版本执行配置语法检查。
4. 解码 `all.txt`，确认六个 VLESS、一个 Hysteria2、一个 AnyTLS URI。
5. 两个正式 URL 均返回 HTTP 200。
6. 订阅目录无法列目录，也无法访问服务端配置和私钥。

## 7. 端到端验收

从两台 VPS 之外测试，优先使用用户日常的中国大陆网络。每个节点至少建立五次新连接，获取独立公网 IP，测试普通 TCP、持续下载，以及协议和客户端支持范围内的 UDP/DNS。

| 节点 | 预期出口 |
|---|---|
| `🇭🇰 香港 RAW` | 入口机 IP |
| `🇭🇰 香港 XHTTP` | 入口机 IP |
| `🇺🇸 美国 RAW` | 出口机 IP |
| `🇺🇸 美国 XHTTP` | 出口机 IP |
| `🇭🇰→🇺🇸 美国经香港 RAW` | 出口机 IP |
| `🇭🇰→🇺🇸 美国经香港 XHTTP` | 出口机 IP |
| `🇺🇸 美国 Hysteria2 备用` | 出口机 IP |
| `🇺🇸 美国 AnyTLS 备用` | 出口机 IP |

同时确认：

- 两台机器的 RAW 与 XHTTP 可独立工作；
- 两个中转身份确实从出口机出网；
- `443/TCP` RAW 与 `443/UDP` Hysteria2 同时工作；
- AnyTLS 可被用户实际客户端使用；
- 国内和私有目标直连，其余目标遵循节点选择；
- 两个订阅均能导入，服务重启后节点仍可用。

若出现短暂成功后失败，必须重复外部测试并检查日志、防火墙、内存和连接资源，不能直接归因于客户端。

## 8. 交付

最终确认全部服务为 `active` 且 `enabled`，监听端口符合矩阵，防火墙规则持久化，两个订阅仍返回 200。

向用户交付：

- `clash.yaml` 与 `all.txt` 地址；
- 八个节点名称和实测出口 IP；
- 两台机器最终 Reality 目标及规划评分；
- Xray、sing-box 与验收所用 Mihomo 版本；
- systemd 服务名和开放端口；
- 与规格不一致的任何调整。

不得交付服务端私钥。
