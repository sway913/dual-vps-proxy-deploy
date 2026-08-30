---
name: dual-vps-proxy-deploy
description: Deploy the proven eight-node Xray and sing-box proxy architecture on two new, otherwise unused VPS hosts, using a nearby ingress VPS for low-latency access and a foreign VPS for the exit IP. Includes direct and relayed nodes, unified Clash and Base64 subscriptions, and end-to-end verification. Use for fresh dual-host deployments, not single-node proxies or general VPN administration.
---

# Dual-VPS Proxy Deployment

Build the final, already validated topology on two fresh servers.

## Required reading

- For planning or provisioning, read [references/specification.md](references/specification.md).
- For any live implementation or validation, also read [references/runbook.md](references/runbook.md) before changing either server.
- When shell access is available, use `scripts/preflight.sh <ingress-host> <exit-host> [ssh-user]` for the initial read-only inventory. Inspect its output; do not treat it as authorization to mutate either host.

## Operating rules

1. Identify the ingress and exit hosts, SSH access, operating systems, occupied ports, and firewall manager. Confirm both machines are fresh and carry no existing proxy or unrelated workload; otherwise stop because the fresh-host precondition is not met.
2. Because Xray, sing-box, Mihomo, XHTTP, VLESS Encryption, and client schemas evolve, verify current syntax and compatibility against official upstream documentation or release notes before generating configs. Do not reuse an old example blindly.
3. Generate fresh per-deployment credentials. Never copy secrets from a previous pair of servers into the skill, logs, source control, or commentary. Avoid printing private keys; show only client credentials and subscription URLs that the user needs.
4. Deploy the final specification directly on both hosts, in parallel where dependencies allow. Validate each configuration before enabling its service.
5. Publish exactly two subscription artifacts: `clash.yaml` and `all.txt`.
6. Require end-to-end tests from an external client. A listening socket, successful local curl, or active systemd unit is not sufficient evidence that a node works from the user's network.

## Completion standard

Report the two subscription URLs, node names, exit IP observed for each node, service enablement, ports/firewall exposure, installed versions, and any deviation from the final specification. Redact server-side private material.
