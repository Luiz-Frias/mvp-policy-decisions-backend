#!/usr/bin/env python3
"""Smoke-test all publicly available GET endpoints via the OpenAPI spec.

Usage:
    python scripts/smoke_test_endpoints.py --base http://localhost:8000 --timeout 5

The script will:
1. Download `/openapi.json`.
2. Iterate through every path/method pair.
3. For GET endpoints it will replace any `{param}` segments with a generic placeholder.
4. Perform the request and record failures (HTTP status >= 400 or exceptions).
5. Exit with status-code 1 if any failures occurred and print a summary.

Note: Auth-protected routes will very likely return 401.  For now
      we accept 401/403 responses as *expected* unless `--require-auth` is set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from typing import Any, Dict, List

import httpx

# ------------------------------
# Placeholder logic for path params
# ------------------------------
_PLACEHOLDERS = {
    "uuid": "00000000-0000-0000-0000-000000000000",
    "id": "1",
    "policyNumber": "POLICY123",
    "quoteId": "1",
}

_PARAM_PATTERN = re.compile(r"{([^}]+)}")


def _substitute_placeholders(path: str) -> str:
    """Replace `{param}` in the URL path with generic placeholders."""

    def _replace(match: re.Match[str]) -> str:  # pragma: no cover
        key = match.group(1)
        # heuristics – if param ends with _id use 1
        if key in _PLACEHOLDERS:
            return _PLACEHOLDERS[key]
        if key.lower().endswith("id"):
            return "1"
        return "test"

    return _PARAM_PATTERN.sub(_replace, path)


async def _fetch_openapi(client: httpx.AsyncClient) -> Dict[str, Any]:
    resp = await client.get("/openapi.json")
    resp.raise_for_status()
    return resp.json()


async def smoke_test(
    base_url: str,
    timeout: float,
    accept_unauthorized: bool,
    sleep_seconds: float = 0.0,
) -> int:
    failures: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        spec = await _fetch_openapi(client)

        paths: Dict[str, Any] = spec.get("paths", {})
        for path_template, methods in paths.items():
            for method, _details in methods.items():
                if method.upper() != "GET":
                    continue

                # Build concrete URL
                concrete_path = _substitute_placeholders(path_template)
                try:
                    resp = await client.request(method.upper(), concrete_path)
                    status = resp.status_code

                    if status >= 400 and not (
                        accept_unauthorized and status in {401, 403}
                    ):
                        failures.append(
                            {
                                "method": method.upper(),
                                "path": path_template,
                                "concrete_path": concrete_path,
                                "status": status,
                            }
                        )
                except Exception as exc:  # pragma: no cover
                    failures.append(
                        {
                            "method": method.upper(),
                            "path": path_template,
                            "concrete_path": concrete_path,
                            "error": str(exc),
                        }
                    )

                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)

    if failures:
        print("FAILED ENDPOINTS (status >=400):")
        print(json.dumps(failures, indent=2))
        return 1

    print("All GET endpoints responded with acceptable status codes.")
    return 0


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Smoke-test API endpoints")
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--allow-unauthorized",
        action="store_true",
        help="Treat 401/403 responses as acceptable (default)",
        default=True,
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Delay between requests seconds to avoid rate-limit",
    )
    args = parser.parse_args()

    rc = asyncio.run(
        smoke_test(
            base_url=args.base,
            timeout=args.timeout,
            accept_unauthorized=args.allow_unauthorized,
            sleep_seconds=args.sleep,
        )
    )
    sys.exit(rc)


if __name__ == "__main__":  # pragma: no cover
    main()
