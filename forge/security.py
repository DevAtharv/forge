from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64url_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


class SecretBox:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def _keystream(self, nonce: bytes, length: int) -> bytes:
        chunks = []
        for index in count():
            block = hashlib.sha256(self._secret + nonce + index.to_bytes(4, "big")).digest()
            chunks.append(block)
            if sum(len(item) for item in chunks) >= length:
                break
        return b"".join(chunks)[:length]

    def encrypt(self, text: str) -> str:
        nonce = hashlib.sha256((text + self._secret.decode("utf-8")).encode("utf-8")).digest()[:16]
        raw = text.encode("utf-8")
        keystream = self._keystream(nonce, len(raw))
        ciphertext = bytes(a ^ b for a, b in zip(raw, keystream))
        return _b64url_encode(nonce + ciphertext)

    def decrypt(self, payload: str) -> str:
        raw = _b64url_decode(payload)
        nonce, ciphertext = raw[:16], raw[16:]
        keystream = self._keystream(nonce, len(ciphertext))
        plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
        return plaintext.decode("utf-8")


class SignedStateCodec:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def encode(self, payload: dict[str, Any], *, expires_in_seconds: int = 900) -> str:
        body = {
            **payload,
            "exp": int((datetime.now(tz=UTC) + timedelta(seconds=expires_in_seconds)).timestamp()),
        }
        raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        return f"{_b64url_encode(raw)}.{_b64url_encode(signature)}"

    def decode(self, token: str) -> dict[str, Any]:
        raw_part, signature_part = token.split(".", maxsplit=1)
        raw = _b64url_decode(raw_part)
        expected = hmac.new(self._secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_part)):
            raise ValueError("Invalid signature.")
        payload = json.loads(raw)
        if int(payload.get("exp", 0)) < int(datetime.now(tz=UTC).timestamp()):
            raise ValueError("State token expired.")
        return payload
