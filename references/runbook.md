# Fresh-server final deployment runbook

Read the topology specification first. This runbook implements the final architecture that has already been proven in use. It assumes both VPS hosts are new, otherwise unused, and authorized for deployment.

## 1. Confirm inputs and fresh-host status

1. Run the read-only preflight script or equivalent checks on both hosts.
2. Confirm OS and architecture, CPU, memory, disk, clock, public IPv4, SSH access, firewall manager, and required port availability.
3. Verify neither machine runs an existing proxy, VPN, tunnel, subscription server, hosting panel, or unrelated workload. If it does, stop; this Skill must not delete or replace it.
4. Test direct reachability between the two VPS addresses.
5. Check current official Xray-core, sing-box, and Mihomo releases and official configuration syntax. Record installed versions.
6. Confirm the target client supports XHTTP, VLESS Encryption, Hysteria2, AnyTLS, and the selected Mihomo schema.

If password login is initially required and the user authorizes its use, install the user's SSH public key and verify key login to both hosts before deployment. Never store or repeat the password.

## 2. Generate final deployment credentials

Use restrictive permissions (`umask 077`) and generate fresh material for this server pair:

- six public VLESS client identities;
- one separate inter-host VLESS identity;
- Reality key pairs and short IDs for each applicable listener;
- unpredictable XHTTP paths and matching VLESS Encryption parameters;
- Hysteria2 and AnyTLS credentials and required TLS material;
- a random subscription path token of at least 32 bytes.

Maintain a mode-`0600` mapping between node name, server, listener, identity/email, route, and client URI. Never place server private keys in subscriptions or chat output.

## 3. Provision the exit VPS

Install current verified Xray and sing-box builds. Configure dedicated paths and systemd units:

- `xray-public.service`: VLESS Reality RAW on `443/TCP` and VLESS Encryption Reality XHTTP on `8443/TCP`;
- `xray-transit.service`: dedicated ingress-to-exit VLESS Encryption Reality RAW/TCP Vision on `36020/TCP`;
- `sing-box-public.service`: Hysteria2 on `443/UDP` and AnyTLS on `2096/TCP`.

The transit listener must use credentials independent of all public nodes. Validate both configs with their installed binaries before enabling services.

Apply exact persistent firewall rules:

- retain SSH;
- allow `443/TCP`, `443/UDP`, `8443/TCP`, and `2096/TCP` publicly;
- allow `36020/TCP` only from the ingress VPS public IPv4 and reject all other sources.

Start and enable the three services. Verify journals and exact listeners. From the ingress VPS, test that the transit connection reaches the exit VPS public IP; do not change either host's default route.

## 4. Provision the ingress VPS

Install a current verified Xray build and configure one public/relay service with:

- RAW Reality Vision inbound on `443/TCP` containing separate direct and relay identities;
- VLESS Encryption Reality XHTTP inbound on `2053/TCP` containing separate direct and relay identities;
- a local direct/freedom outbound;
- the dedicated VLESS RAW/TCP outbound to exit `36020/TCP`;
- user/email routing that sends only the two relay identities to the inter-host outbound.

Validate the config before starting. Apply persistent firewall rules that retain SSH and allow `443/TCP`, `2053/TCP`, and subscription `36010/TCP`. Start and enable the ingress Xray service.

Verify locally and through controlled test clients that:

- direct RAW and XHTTP identities exit via the ingress IP;
- relay RAW and XHTTP identities exit via the exit IP;
- no relay identity falls back silently to ingress-direct egress.

## 5. Publish the two subscriptions on ingress

Create and enable a minimal `proxy-subscription.service` listening on ingress port `36010/TCP`. Use the random path token and publish only:

```text
http://<ingress-ip>:36010/<random-token>/clash.yaml
http://<ingress-ip>:36010/<random-token>/all.txt
```

Requirements:

1. `clash.yaml` contains all eight final nodes with unique names.
2. The default selected node is `🇭🇰 香港 RAW`.
3. LAN/private and mainland China destinations are direct; other traffic uses the selected proxy.
4. The automatic latency group contains only `🇭🇰 香港 RAW`, `🇺🇸 美国 RAW`, and `🇭🇰→🇺🇸 美国经香港 RAW`.
5. XHTTP, Hysteria2, and AnyTLS nodes remain manually selectable.
6. `all.txt` is Base64-encoded newline-separated content containing six `vless://`, one `hysteria2://`, and one `anytls://` URI.
7. Do not expose directory listings, server configs, generators containing secrets, credential manifests, certificates' private keys, or Reality private keys.

Validate `clash.yaml` with the target Mihomo version. Decode `all.txt` and assert its scheme counts before publishing. Confirm both URLs return HTTP 200.

## 6. End-to-end acceptance

Test from a machine outside both VPS networks, preferably through the user's normal mainland China connection. For every node:

- establish at least five fresh connections;
- fetch an independent public-IP endpoint through the proxy;
- verify ordinary TCP browsing and a sustained transfer;
- verify UDP/DNS where the protocol and client support it;
- record latency and failures without promising exact latency.

Expected exit mapping:

| Node | Expected exit |
|---|---|
| `🇭🇰 香港 RAW` | ingress VPS IP |
| `🇭🇰 香港 XHTTP` | ingress VPS IP |
| `🇺🇸 美国 RAW` | exit VPS IP |
| `🇺🇸 美国 XHTTP` | exit VPS IP |
| `🇭🇰→🇺🇸 美国经香港 RAW` | exit VPS IP |
| `🇭🇰→🇺🇸 美国经香港 XHTTP` | exit VPS IP |
| `🇺🇸 美国 Hysteria2 备用` | exit VPS IP |
| `🇺🇸 美国 AnyTLS 备用` | exit VPS IP |

Also confirm:

- the two direct protocols on each VPS work independently;
- both relay identities are routed to exit;
- Hysteria2 `443/UDP` and RAW `443/TCP` coexist without collision;
- AnyTLS works in the user's actual client;
- China/private routing is direct and foreign routing follows the selected group;
- both subscriptions import cleanly and survive service restarts.

A brief success followed by failure requires repeated external tests plus journal, firewall, and resource inspection. Do not dismiss it as client error.

## 7. Final handoff

Check that every intended unit is `active` and `enabled`, listeners exactly match the final matrix, firewall rules persist, and both subscriptions still return 200 and import successfully.

Give the user:

- the canonical `clash.yaml` and `all.txt` URLs;
- all eight node names and observed exit IPs;
- installed Xray and sing-box versions plus the Mihomo version used for validation;
- service names and exposed ports;
- any deviation from the final specification.

Do not include server private keys.
