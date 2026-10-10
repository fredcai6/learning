"""Who is asking. Cloudflare Access signs in at the edge; this checks its token.

Access puts a signed JWT in the `Cf-Access-Jwt-Assertion` header of every
request it lets through. The token is verified against Access's public keys,
for this application's audience tag, and its email is looked up in
learners.toml. Anything short of that is refused: the app fails closed, so a
path accidentally left outside the Access policy shows nothing.

The keys are read from a JWKS file that a host-side timer refreshes
(deploy/fetch-access-certs.sh); this container has no route to the internet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import jwt
from jwt.algorithms import RSAAlgorithm

log = logging.getLogger(__name__)


class Keys:
    """Public keys from the JWKS file, reloaded when the file changes."""

    def __init__(self, path: Path | None):
        self.path = path
        self._mtime: float | None = None
        self._keys: dict[str, object] = {}

    def get(self) -> dict[str, object]:
        if self.path is None or not self.path.is_file():
            return {}
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime:
            data = json.loads(self.path.read_text())
            self._keys = {k["kid"]: RSAAlgorithm.from_jwk(json.dumps(k)) for k in data.get("keys", [])}
            self._mtime = mtime
        return self._keys


def _unverified(token: str) -> dict:
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return {}


def email_from_token(token: str | None, keys: Keys, audience: str | None, issuer: str | None) -> str | None:
    if not token:
        return None
    if not audience or not issuer:
        # Setup aid: the audience tag and issuer are what this deployment
        # needs configured, and they are not secrets.
        claims = _unverified(token)
        log.warning("Access token arrived but LEARN_ACCESS_AUD/ISSUER are unset; token aud=%s iss=%s",
                    claims.get("aud"), claims.get("iss"))
        return None
    available = keys.get()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = available.get(kid)
        if key is None:
            log.warning("Access token signed with unknown key %s; are the certs current?", kid)
            return None
        claims = jwt.decode(token, key=key, algorithms=["RS256"], audience=audience, issuer=issuer,
                            options={"require": ["exp", "iat", "aud", "iss"]})
    except jwt.PyJWTError as exc:
        claims = _unverified(token)
        log.warning("rejected Access token: %s (aud=%s iss=%s)", exc, claims.get("aud"), claims.get("iss"))
        return None
    email = claims.get("email")
    return email if isinstance(email, str) else None
