"""Single-operator token authentication.

Auth is always on: if BSOS_API_TOKEN is unset, a token is generated at boot,
written to var/api-token.txt (0600) and the generation is ledgered. Every
/api/* route except /api/health requires it — as a Bearer header, or as a
`?token=` query parameter for the two places a browser cannot set headers
(EventSource for the SSE feed, <img> tags for asset/concept previews).

Without this layer, every kernel guarantee evaporates at the network
boundary: the ledger would record "owner" for whoever reached port 8000.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

OPEN_PATHS = {"/api/health"}


def resolve_token(var_dir: Path, ledger=None) -> str:
    token = os.environ.get("BSOS_API_TOKEN", "").strip()
    if token:
        return token
    token_file = var_dir / "api-token.txt"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    token_file.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass  # e.g. Windows: chmod is advisory there
    if ledger:
        ledger.append("auth_token_generated", actor="system", outcome="ok",
                      data={"path": str(token_file)})
    return token


def _extract(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.query_params.get("token", "")


def make_auth_middleware(token: str):
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api") or path in OPEN_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        supplied = _extract(request)
        if not supplied or not hmac.compare_digest(supplied, token):
            return JSONResponse(
                status_code=401,
                content={"detail": {"kind": "unauthenticated",
                                    "message": "missing or invalid API token"}},
            )
        return await call_next(request)

    return auth_middleware
