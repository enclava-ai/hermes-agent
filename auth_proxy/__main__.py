"""CLI entrypoint:  python -m auth_proxy [--listen ...] [--upstream ...]"""
from __future__ import annotations

import argparse

from auth_proxy.server import run


def _parse_host_port(value: str, default_host: str, default_port: int) -> tuple[str, int]:
    if ":" in value:
        host, _, port = value.rpartition(":")
        return host or default_host, int(port)
    if value.isdigit():
        return default_host, int(value)
    return value, default_port


def main() -> None:
    p = argparse.ArgumentParser(
        prog="hermes-auth-proxy",
        description="Username/password gate in front of the Hermes web dashboard.",
    )
    p.add_argument(
        "--listen", default="0.0.0.0:9120",
        help="host:port to bind the proxy to (default 0.0.0.0:9120)",
    )
    p.add_argument(
        "--upstream", default="127.0.0.1:9119",
        help="host:port of the upstream `hermes web` server (default 127.0.0.1:9119)",
    )
    args = p.parse_args()

    listen_host, listen_port = _parse_host_port(args.listen, "0.0.0.0", 9120)
    up_host, up_port = _parse_host_port(args.upstream, "127.0.0.1", 9119)
    run(listen_host, listen_port, up_host, up_port)


if __name__ == "__main__":
    main()
