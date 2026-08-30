#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <ingress-host> <exit-host> [ssh-user]" >&2
  exit 2
fi

ingress_host=$1
exit_host=$2
ssh_user=${3:-root}
ssh_options=(-o BatchMode=yes -o ConnectTimeout=10)

inspect_host() {
  local role=$1
  local host=$2

  echo "===== ${role}: ${host} ====="
  ssh "${ssh_options[@]}" "${ssh_user}@${host}" 'sh -s' <<'REMOTE'
set -eu

echo '[system]'
uname -a
if [ -r /etc/os-release ]; then
  sed -n '1,12p' /etc/os-release
fi
command -v getconf >/dev/null 2>&1 && getconf LONG_BIT || true
command -v nproc >/dev/null 2>&1 && nproc || true
free -h 2>/dev/null || true
df -h / 2>/dev/null || true

echo '[time]'
date -Is 2>/dev/null || date

echo '[listeners]'
ss -lntup 2>/dev/null || netstat -lntup 2>/dev/null || true

echo '[deployment binaries already present]'
for executable in xray sing-box mihomo; do
  if command -v "$executable" >/dev/null 2>&1; then
    command -v "$executable"
    "$executable" version 2>/dev/null | sed -n '1,3p' || true
  fi
done

echo '[existing workload indicators]'
systemctl list-unit-files --no-legend 2>/dev/null \
  | grep -Ei 'xray|sing-box|proxy|docker|containerd|nginx|apache|caddy|(^|[[:space:]])xr\.service|(^|[[:space:]])sb\.service' \
  || true
systemctl list-units --type=service --all --no-legend 2>/dev/null \
  | grep -Ei 'xray|sing-box|proxy|docker|containerd|nginx|apache|caddy|xr\.service|sb\.service' \
  || true

echo '[firewall managers]'
for executable in nft iptables ufw firewall-cmd; do
  command -v "$executable" 2>/dev/null || true
done

REMOTE
}

inspect_host ingress "$ingress_host"
inspect_host exit "$exit_host"
