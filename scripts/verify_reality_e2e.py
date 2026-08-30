#!/usr/bin/env python3
"""从外部主机启动临时 Xray 客户端并核对多个 Reality 节点的出口 IP。"""

from __future__ import annotations

import argparse
import ipaddress
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


def parse_probe(raw: str) -> tuple[str, int, str]:
    parts = raw.rsplit("=", 2)
    if len(parts) != 3 or not parts[0].strip():
        raise argparse.ArgumentTypeError("探测格式必须是 名称=本地端口=预期IPv4")
    name, port_text, expected = (part.strip() for part in parts)
    try:
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise ValueError
        address = ipaddress.ip_address(expected)
        if address.version != 4:
            raise ValueError
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"无效探测参数：{raw}") from exc
    return name, port, expected


def wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="外部验证 Xray REALITY 节点的真实出口")
    parser.add_argument("--xray", required=True, help="Xray 可执行文件")
    parser.add_argument("--config", required=True, help="仅监听 127.0.0.1 的临时客户端 JSON")
    parser.add_argument(
        "--probe",
        action="append",
        type=parse_probe,
        required=True,
        help="名称=本地SOCKS端口=预期IPv4；可重复",
    )
    parser.add_argument("--rounds", type=int, default=5, help="每个入口的新连接轮数，默认 5")
    parser.add_argument("--interval", type=float, default=2.0, help="每轮间隔秒数，默认 2")
    parser.add_argument("--timeout", type=float, default=20.0, help="单次 curl 超时秒数")
    parser.add_argument("--url", default="https://api.ipify.org", help="返回纯文本公网 IP 的 HTTPS URL")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.rounds <= 20:
        print("--rounds 必须在 1 到 20 之间", file=sys.stderr)
        return 2
    if not 0 <= args.interval <= 60 or not 1 <= args.timeout <= 120:
        print("--interval 或 --timeout 超出允许范围", file=sys.stderr)
        return 2

    xray = Path(args.xray)
    config = Path(args.config)
    if not xray.is_file() or not config.is_file():
        print("Xray 或客户端配置不存在", file=sys.stderr)
        return 2
    if not shutil.which("curl"):
        print("未找到 curl", file=sys.stderr)
        return 2
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
        inbounds = payload.get("inbounds", [])
        if (
            not isinstance(inbounds, list)
            or not inbounds
            or any(not isinstance(item, dict) for item in inbounds)
        ):
            print("客户端 inbounds 格式无效", file=sys.stderr)
            return 2
        configured_ports = {int(item.get("port", 0)) for item in inbounds}
        if any(
            item.get("listen") not in {"127.0.0.1", "::1", "localhost"}
            for item in inbounds
        ):
            print("客户端所有入站必须显式监听回环地址", file=sys.stderr)
            return 2
        if any(port not in configured_ports for _, port, _ in args.probe):
            print("探测端口未出现在客户端配置中", file=sys.stderr)
            return 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print("无法解析客户端 JSON", file=sys.stderr)
        return 2
    try:
        validation = subprocess.run(
            [str(xray), "run", "-test", "-config", str(config)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Xray 客户端配置校验未完成", file=sys.stderr)
        return 2
    if validation.returncode:
        print("Xray 客户端配置校验失败", file=sys.stderr)
        return 2

    try:
        process = subprocess.Popen(
            [str(xray), "run", "-config", str(config)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        print("无法启动 Xray 临时客户端", file=sys.stderr)
        return 2
    results: list[dict[str, object]] = []
    try:
        for _, port, _ in args.probe:
            if not wait_for_port(port, 5.0):
                print(f"本地 SOCKS 端口 {port} 未就绪", file=sys.stderr)
                return 1
        for round_number in range(1, args.rounds + 1):
            for name, port, expected in args.probe:
                completed = subprocess.run(
                    [
                        "curl",
                        "-4",
                        "-fsS",
                        "--max-time",
                        str(args.timeout),
                        "--socks5-hostname",
                        f"127.0.0.1:{port}",
                        args.url,
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                actual = completed.stdout.strip()
                ok = completed.returncode == 0 and actual == expected
                results.append(
                    {
                        "round": round_number,
                        "name": name,
                        "port": port,
                        "expected_ip": expected,
                        "actual_ip": actual,
                        "ok": ok,
                    }
                )
                if not args.json:
                    print(f"第{round_number}轮 {name}: {'通过' if ok else '失败'}")
            if args.interval and round_number < args.rounds:
                time.sleep(args.interval)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    passed = all(bool(item["ok"]) for item in results)
    if args.json:
        print(json.dumps({"passed": passed, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"REALITY_E2E={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
