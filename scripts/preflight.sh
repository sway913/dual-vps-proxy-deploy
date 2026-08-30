#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "用法：$0 <入口机> <出口机> [SSH用户]" >&2
  exit 2
fi

ingress_host=$1
exit_host=$2
ssh_user=${3:-root}
ssh_options=(-o BatchMode=yes -o ConnectTimeout=10)

inspect_host() {
  local role=$1
  local host=$2

  echo "===== ${role}：${host} ====="
  ssh "${ssh_options[@]}" "${ssh_user}@${host}" 'sh -s' <<'REMOTE'
set -eu

echo '[系统]'
uname -a
if [ -r /etc/os-release ]; then
  sed -n '1,12p' /etc/os-release
fi
command -v getconf >/dev/null 2>&1 && getconf LONG_BIT || true
command -v nproc >/dev/null 2>&1 && nproc || true
free -h 2>/dev/null || true
df -h / 2>/dev/null || true

echo '[时钟]'
date -Is 2>/dev/null || date

echo '[监听端口]'
ss -lntup 2>/dev/null || netstat -lntup 2>/dev/null || true

echo '[已存在的部署程序]'
for executable in xray sing-box mihomo; do
  if command -v "$executable" >/dev/null 2>&1; then
    command -v "$executable"
    "$executable" version 2>/dev/null | sed -n '1,3p' || true
  fi
done

echo '[既有业务迹象]'
systemctl list-unit-files --no-legend 2>/dev/null \
  | grep -Ei 'xray|sing-box|proxy|docker|containerd|nginx|apache|caddy|(^|[[:space:]])xr\.service|(^|[[:space:]])sb\.service' \
  || true
systemctl list-units --type=service --all --no-legend 2>/dev/null \
  | grep -Ei 'xray|sing-box|proxy|docker|containerd|nginx|apache|caddy|xr\.service|sb\.service' \
  || true

echo '[防火墙工具]'
for executable in nft iptables ufw firewall-cmd; do
  command -v "$executable" 2>/dev/null || true
done
REMOTE
}

inspect_host 入口机 "$ingress_host"
inspect_host 出口机 "$exit_host"
