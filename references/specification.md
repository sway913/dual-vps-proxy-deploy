# Reusable topology specification

This is the final validated architecture for two new, otherwise unused servers; it is not permission to change them. Substitute region labels when the ingress or exit VPS is elsewhere. Reassign a default port only when inventory shows a collision or the user requests another layout, and reflect every change in clients, firewalls, and acceptance tests.

## Inputs to resolve

Resolve these from the user or read-only inspection before implementation:

- ingress VPS address and SSH access;
- exit VPS address and SSH access;
- OS, architecture, public address family, firewall/panel, and occupied ports;
- desired display-region names;
- whether the subscription should initially be HTTP by ingress IP or HTTPS through a user-owned domain;
- client support for XHTTP, VLESS Encryption, Hysteria2, AnyTLS, and the chosen Mihomo schema.

Do not request secrets already available through working SSH. If password login is the only access method and the user authorizes it, install the user's public key, verify key login in a separate session, and only then reduce dependence on passwords. Never persist or repeat an SSH password.

## Default node matrix

| Node | Public listener | Egress | Implementation |
|---|---:|---|---|
| `🇭🇰 香港 RAW` | ingress `443/TCP` | ingress VPS | VLESS + Reality + RAW/TCP + Vision |
| `🇭🇰 香港 XHTTP` | ingress `2053/TCP` | ingress VPS | VLESS Encryption + Reality + XHTTP |
| `🇺🇸 美国 RAW` | exit `443/TCP` | exit VPS | VLESS + Reality + RAW/TCP + Vision |
| `🇺🇸 美国 XHTTP` | exit `8443/TCP` | exit VPS | VLESS Encryption + Reality + XHTTP |
| `🇭🇰→🇺🇸 美国经香港 RAW` | ingress `443/TCP` | exit VPS | distinct ingress user routed through the inter-host VLESS outbound |
| `🇭🇰→🇺🇸 美国经香港 XHTTP` | ingress `2053/TCP` | exit VPS | distinct ingress user routed through the same inter-host outbound |
| `🇺🇸 美国 Hysteria2 备用` | exit `443/UDP` | exit VPS | sing-box Hysteria2 |
| `🇺🇸 美国 AnyTLS 备用` | exit `2096/TCP` | exit VPS | sing-box AnyTLS |

TCP and UDP may use the same numeric port. On the ingress host, RAW direct and relayed clients share one inbound and are distinguished by unique client identity/email; XHTTP does the same on its inbound. Route only the two relay identities to the inter-host outbound. Direct identities use the local freedom/direct outbound.

## Inter-host transport

Default to a dedicated Xray VLESS Encryption + Reality + RAW/TCP + Vision hop from ingress to exit on `36020/TCP`:

- use fresh credentials unrelated to the public listeners;
- expose it only to the ingress VPS public IP in both persistent and runtime firewalls;
- use an independent systemd unit and config, such as `xray-transit.service`;
- do not change either host's default route.

This keeps routing entirely within Xray.

## Service separation

Use descriptive units:

- ingress: one Xray public/relay service and `proxy-subscription.service`;
- exit: `xray-public.service`, `xray-transit.service`, and `sing-box-public.service`.

## Credential and Reality rules

- Set restrictive permissions before writing secrets (`umask 077` or equivalent).
- Generate unique UUIDs for every logical client, new Reality X25519 key pairs and short IDs, unpredictable XHTTP paths, protocol passwords, certificates/keys where required, and at least a 32-byte random subscription path token.
- Generate VLESS Encryption material using commands supported by the installed Xray version; confirm both server and client use the exact same negotiated value.
- Use `hkust.edu.hk:443` for ingress Reality listeners and `apple.com:443` for exit Reality listeners, including transit. Validate TLS 1.3 reachability, matching SNI/certificate, stable response, and acceptable latency from the new hosts before enabling services.
- Avoid optional XHTTP multiplex/reuse settings unless current official guidance and client testing justify them.

## Firewall exposure

Retain SSH and management access. The expected new openings are:

- ingress: `443/TCP`, `2053/TCP`, and the chosen subscription port (default `36010/TCP` while IP-hosted);
- exit: `443/TCP`, `443/UDP`, `8443/TCP`, and `2096/TCP`;
- exit transit: `36020/TCP` accepted from the ingress public IP and dropped for all other sources.

Update the actual persistent firewall authority in use (for example nftables, iptables persistence, UFW, firewalld, or a hosting panel), not only ephemeral runtime rules. Avoid broad port ranges when exact rules suffice.

## Subscription contract

Host subscriptions on the ingress VPS unless the user says otherwise. Use an unguessable path and initially publish either:

```text
http://<ingress-ip>:36010/<random-token>/clash.yaml
http://<ingress-ip>:36010/<random-token>/all.txt
```

or the HTTPS equivalents after domain/TLS setup.

`clash.yaml` contains all eight nodes. `all.txt` is the Base64 encoding of newline-separated share URIs for all eight nodes: six VLESS, one Hysteria2, and one AnyTLS. It is not a VLESS-only subscription despite being Base64.

Clash policy defaults:

- selected/default proxy: `🇭🇰 香港 RAW`;
- LAN/private destinations and mainland China destinations: direct;
- other traffic: selected proxy;
- automatic latency group: only the three RAW nodes (ingress RAW, exit RAW, relayed RAW);
- XHTTP, Hysteria2, and AnyTLS remain manually selectable fallbacks.

Keep the subscription service narrowly scoped. For this final IP-hosted form, listen on the ingress public subscription port.
