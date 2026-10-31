"""API-key gate for calls into this service. Only meant to keep this a
private, same-host/trusted-network service (Vimo-ai's NestJS process calling
it over localhost) from being callable by anything else that can reach the
port -- not a general-purpose auth system (no users/roles/scopes).

SUBTITLE_SERVICE_API_KEY must be set for the app to start; there is no
"auth disabled if unset" fallback, so a missing key fails loudly at boot
instead of silently serving unauthenticated.
"""
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

_API_KEY_HEADER_NAME = 'X-API-Key'
_api_key_header = APIKeyHeader(name=_API_KEY_HEADER_NAME, auto_error=False)

# Read and validated once at import time (i.e. at process startup, before
# uvicorn ever binds a port) rather than per-request -- a missing key fails
# the whole process immediately instead of only surfacing on the first
# incoming call.
_EXPECTED_KEY = os.environ.get('SUBTITLE_SERVICE_API_KEY')
if not _EXPECTED_KEY:
    raise RuntimeError(
        'SUBTITLE_SERVICE_API_KEY is not set. Refusing to start without it -- '
        'this service has no other access control. Set it in the environment '
        '(see .env.example) before running uvicorn.'
    )


def require_api_key(provided: str = Depends(_api_key_header)) -> None:
    # Constant-time compare -- a naive `!=` leaks timing information an
    # attacker could use to guess the key byte-by-byte; low-stakes here
    # (private/local service) but costs nothing to do correctly.
    if not provided or not secrets.compare_digest(provided, _EXPECTED_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or missing X-API-Key header.')
