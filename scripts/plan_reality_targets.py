#!/usr/bin/env python3
"""在目标 VPS 本机发现、验证并排序 Xray REALITY 伪装目标。"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import math
import re
import shutil
import socket
import ssl
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = {
    "ingress": [
        "hkust.edu.hk",
        "www.hku.hk",
        "www.cuhk.edu.hk",
        "www.polyu.edu.hk",
        "www.cityu.edu.hk",
        "www.hkex.com.hk",
        "www.gov.hk",
    ],
    "exit": [
        "apple.com",
        "www.apple.com",
        "www.microsoft.com",
        "www.amazon.com",
        "www.ibm.com",
        "www.oracle.com",
        "www.intel.com",
        "www.yahoo.com",
    ],
}

# REALITY 官方文档明确提示 Cloudflare 一类特殊 CDN 目标可能形成转发风险。
RISK_ASNS = {13335: "Cloudflare"}
ROLE_ALIASES = {
    "ingress": "ingress",
    "入口": "ingress",
    "入口机": "ingress",
    "香港": "ingress",
    "exit": "exit",
    "出口": "exit",
    "出口机": "exit",
    "美国": "exit",
}


def direct_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "dual-vps-reality-planner/1"})
    with direct_opener().open(request, timeout=timeout) as response:
        return json.load(response)


def current_public_ip(timeout: float) -> str:
    payload = fetch_json("https://stat.ripe.net/data/whats-my-ip/data.json", timeout)
    value = str(payload.get("data", {}).get("ip", ""))
    ipaddress.ip_address(value)
    return value


_asn_cache: dict[str, tuple[set[int], list[str]]] = {}


def lookup_asns(ip: str, timeout: float) -> tuple[set[int], list[str]]:
    if ip in _asn_cache:
        return _asn_cache[ip]
    resource = urllib.parse.quote(ip, safe="")
    payload = fetch_json(
        f"https://stat.ripe.net/data/prefix-overview/data.json?resource={resource}", timeout
    )
    values = payload.get("data", {}).get("asns", [])
    asns: set[int] = set()
    holders: list[str] = []
    for item in values:
        if isinstance(item, dict):
            if item.get("asn") is not None:
                asns.add(int(item["asn"]))
            if item.get("holder"):
                holders.append(str(item["holder"]))
        elif item is not None:
            asns.add(int(item))
    result = (asns, holders)
    _asn_cache[ip] = result
    return result


def normalize_domain(raw: str) -> str:
    value = raw.strip().lower().rstrip(".")
    if not value or value.startswith("#"):
        return ""
    if ":" in value and value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        if port.isdigit():
            value = host
    if len(value) > 253 or not re.fullmatch(r"[a-z0-9.-]+", value):
        raise ValueError(f"无效域名：{raw}")
    labels = value.split(".")
    if len(labels) < 2 or any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        for label in labels
    ):
        raise ValueError(f"无效域名：{raw}")
    return value


def resolve_ipv4(domain: str) -> list[str]:
    addresses: list[str] = []
    for item in socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM):
        ip = item[4][0]
        if ip not in addresses:
            addresses.append(ip)
    return addresses[:4]


def tls_probe(domain: str, ip: str, timeout: float) -> dict[str, Any]:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(["h2", "http/1.1"])
    started = time.monotonic()
    with socket.create_connection((ip, 443), timeout=timeout) as plain:
        plain.settimeout(timeout)
        with context.wrap_socket(plain, server_hostname=domain) as tls_socket:
            latency_ms = (time.monotonic() - started) * 1000
            certificate = tls_socket.getpeercert()
            sans = sorted(
                {
                    str(value).lower().rstrip(".")
                    for key, value in certificate.get("subjectAltName", [])
                    if key == "DNS" and value
                }
            )
            return {
                "ip": ip,
                "latency_ms": round(latency_ms, 1),
                "tls": tls_socket.version() or "",
                "alpn": tls_socket.selected_alpn_protocol() or "",
                "sans": sans,
            }


def discover_sans(seeds: list[str], timeout: float, limit: int) -> list[str]:
    if limit <= 0:
        return []
    discovered: list[str] = []
    for domain in seeds:
        try:
            addresses = resolve_ipv4(domain)
            if not addresses:
                continue
            result = tls_probe(domain, addresses[0], timeout)
            for san in result["sans"]:
                if "*" in san:
                    continue
                try:
                    san = normalize_domain(san)
                except ValueError:
                    continue
                if san and san not in seeds and san not in discovered:
                    discovered.append(san)
                    if len(discovered) >= limit:
                        return discovered
        except (OSError, ssl.SSLError, socket.gaierror):
            continue
    return discovered


def xray_tls_ping(xray: str | None, domain: str, timeout: float) -> dict[str, Any]:
    if not xray:
        return {"available": False}
    try:
        process = subprocess.run(
            [xray, "tls", "ping", domain],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(12.0, timeout * 2),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": True, "sni_ok": False, "error": "xray tls ping 执行失败"}
    output = process.stdout
    sni_section = output.split("Pinging with SNI", 1)[-1]
    chain_match = re.search(r"Certificate chain's total length:\s+(\d+)", sni_section)
    return {
        "available": True,
        "sni_ok": "Handshake succeeded" in sni_section,
        "tls13": "TLS 1.3" in sni_section,
        "post_quantum": bool(
            re.search(r"Post-Quantum key exchange:\s+true", sni_section, re.IGNORECASE)
        ),
        "certificate_chain_bytes": int(chain_match.group(1)) if chain_match else None,
        "returncode": process.returncode,
    }


def probe_candidate(
    domain: str,
    probes: int,
    timeout: float,
    host_asns: set[int],
    xray: str | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "domain": domain,
        "successes": 0,
        "probes": probes,
        "latencies_ms": [],
        "ips": [],
        "target_asns": [],
        "alpn": [],
        "tls13": False,
        "same_asn": False,
        "risk": "",
        "qualified": False,
        "score": 0.0,
        "error": "",
        "median_latency_ms": None,
        "certificate_sans": [],
        "asn_holders": [],
        "xray_tls_ping": {"available": False},
        "verdict": "不合格",
    }
    try:
        addresses = resolve_ipv4(domain)
    except socket.gaierror as exc:
        result["error"] = f"DNS 失败：{exc}"
        return result
    if not addresses:
        result["error"] = "没有 IPv4 地址"
        return result
    result["ips"] = addresses

    sans: set[str] = set()
    alpns: set[str] = set()
    tls13 = True
    for index in range(probes):
        ip = addresses[index % len(addresses)]
        try:
            sample = tls_probe(domain, ip, timeout)
            result["successes"] += 1
            result["latencies_ms"].append(sample["latency_ms"])
            if sample["alpn"]:
                alpns.add(sample["alpn"])
            tls13 = tls13 and sample["tls"] == "TLSv1.3"
            sans.update(sample["sans"])
        except (OSError, ssl.SSLError, socket.gaierror) as exc:
            result["error"] = str(exc)
    result["alpn"] = sorted(alpns)
    result["tls13"] = tls13 and result["successes"] > 0
    result["certificate_sans"] = sorted(sans)

    target_asns: set[int] = set()
    holders: list[str] = []
    for ip in addresses:
        try:
            asns, names = lookup_asns(ip, timeout)
            target_asns.update(asns)
            holders.extend(names)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            continue
    result["target_asns"] = sorted(target_asns)
    result["asn_holders"] = sorted(set(holders))
    result["same_asn"] = bool(host_asns & target_asns)
    risky = sorted(target_asns & set(RISK_ASNS))
    if risky:
        result["risk"] = ", ".join(f"AS{asn} {RISK_ASNS[asn]}" for asn in risky)

    xray_result = xray_tls_ping(xray, domain, timeout)
    result["xray_tls_ping"] = xray_result
    required_successes = math.ceil(probes * 2 / 3)
    xray_ok = not xray_result.get("available") or (
        xray_result.get("sni_ok") and xray_result.get("tls13")
    )
    result["qualified"] = (
        result["successes"] >= required_successes and result["tls13"] and xray_ok
    )

    score = 40.0 * result["successes"] / probes
    if result["same_asn"]:
        score += 30.0
    if "h2" in alpns:
        score += 10.0
    if result["latencies_ms"]:
        median_ms = statistics.median(result["latencies_ms"])
        result["median_latency_ms"] = round(median_ms, 1)
        score += max(0.0, 20.0 - median_ms / 25.0)
    else:
        result["median_latency_ms"] = None
    if xray_result.get("post_quantum"):
        score += 5.0
    if result["risk"]:
        score -= 50.0
    if not result["qualified"]:
        score -= 100.0
    result["score"] = round(score, 1)
    if not result["qualified"]:
        result["verdict"] = "不合格"
    elif result["risk"]:
        result["verdict"] = "风险目标"
    elif result["same_asn"]:
        result["verdict"] = "优先推荐"
    else:
        result["verdict"] = "可用"
    return result


def read_candidate_file(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="自动规划 Xray REALITY 伪装目标", add_help=False
    )
    parser._positionals.title = "位置参数"
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助并退出")
    parser.add_argument("role", help="ingress/入口机 或 exit/出口机")
    parser.add_argument("--candidate", action="append", default=[], help="追加候选域名，可重复")
    parser.add_argument("--candidate-file", help="候选文件，每行一个域名，# 开头为注释")
    parser.add_argument("--no-defaults", action="store_true", help="不加载角色默认候选")
    parser.add_argument("--probes", type=int, default=3, help="每个候选的 TLS 探测次数")
    parser.add_argument("--timeout", type=float, default=6.0, help="单次网络操作超时秒数")
    parser.add_argument("--san-limit", type=int, default=12, help="从证书 SAN 扩展的候选上限")
    parser.add_argument("--workers", type=int, default=4, help="并发探测数，默认 4")
    parser.add_argument("--xray", help="Xray 可执行文件路径；默认从 PATH 查找")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    role = ROLE_ALIASES.get(args.role.lower())
    if not role:
        print("角色必须是 ingress/入口机 或 exit/出口机", file=sys.stderr)
        return 2
    if args.probes < 1 or args.probes > 10:
        print("--probes 必须在 1 到 10 之间", file=sys.stderr)
        return 2
    if args.workers < 1 or args.workers > 16:
        print("--workers 必须在 1 到 16 之间", file=sys.stderr)
        return 2
    if args.san_limit < 0 or args.san_limit > 100:
        print("--san-limit 必须在 0 到 100 之间", file=sys.stderr)
        return 2

    raw_candidates = [] if args.no_defaults else list(DEFAULT_CANDIDATES[role])
    raw_candidates.extend(args.candidate)
    if args.candidate_file:
        raw_candidates.extend(read_candidate_file(args.candidate_file))
    candidates: list[str] = []
    try:
        for raw in raw_candidates:
            domain = normalize_domain(raw)
            if domain and domain not in candidates:
                candidates.append(domain)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    candidates.extend(
        domain
        for domain in discover_sans(candidates, args.timeout, args.san_limit)
        if domain not in candidates
    )

    try:
        host_ip = current_public_ip(args.timeout)
        host_asns, host_holders = lookup_asns(host_ip, args.timeout)
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"无法获取本机公网 IP/ASN：{exc}", file=sys.stderr)
        return 1

    xray = args.xray or shutil.which("xray")
    if xray and not Path(xray).is_file():
        print(f"Xray 文件不存在：{xray}", file=sys.stderr)
        return 2

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                probe_candidate, domain, args.probes, args.timeout, host_asns, xray
            )
            for domain in candidates
        ]
        results = [future.result() for future in futures]
    results.sort(key=lambda item: (item["score"], item["domain"]), reverse=True)
    selectable = [item for item in results if item["qualified"] and not item["risk"]]
    selected = selectable[0] if selectable else None
    payload = {
        "role": role,
        "host_ip": host_ip,
        "host_asns": sorted(host_asns),
        "host_asn_holders": host_holders,
        "xray": xray,
        "selected_target": f"{selected['domain']}:443" if selected else None,
        "server_name": selected["domain"] if selected else None,
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        host_asn_text = ",".join(f"AS{asn}" for asn in sorted(host_asns)) or "未知"
        print(f"本机公网 IP：{host_ip}")
        print(f"本机 ASN：{host_asn_text}")
        if host_holders:
            print(f"ASN 名称：{', '.join(host_holders)}")
        print(f"Xray tls ping：{xray or '未找到，仅执行系统 TLS 校验'}")
        print()
        print("分数\t结论\t成功\t中位延迟\t同ASN\tALPN\t目标ASN\t域名")
        for item in results:
            latency = (
                f"{item['median_latency_ms']}ms"
                if item.get("median_latency_ms") is not None
                else "-"
            )
            target_asn = ",".join(f"AS{asn}" for asn in item["target_asns"]) or "未知"
            alpn = ",".join(item["alpn"]) or "-"
            risk = f"({item['risk']})" if item["risk"] else ""
            print(
                f"{item['score']:.1f}\t{item['verdict']}{risk}\t"
                f"{item['successes']}/{item['probes']}\t{latency}\t"
                f"{'是' if item['same_asn'] else '否'}\t{alpn}\t{target_asn}\t{item['domain']}"
            )
        print()
        if selected:
            print(f"SELECTED_TARGET={selected['domain']}:443")
            print(f"SERVER_NAME={selected['domain']}")
            print(f"SELECTED_SCORE={selected['score']:.1f}")
            print(f"SELECTED_VERDICT={selected['verdict']}")
        else:
            print("没有通过硬性检查且可自动采用的候选目标。", file=sys.stderr)

    return 0 if selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
