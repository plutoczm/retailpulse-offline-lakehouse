"""Serve the RetailPulse dashboard from the local dashboard directory."""

from __future__ import annotations

import argparse
import http.server
import socketserver
from functools import partial
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve RetailPulse dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8508)
    parser.add_argument("--directory", default="dashboard")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = Path(args.directory).resolve()
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"RetailPulse dashboard: http://{args.host}:{args.port}")
        print(f"Serving directory: {directory}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
