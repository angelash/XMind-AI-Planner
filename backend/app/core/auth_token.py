from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('utf-8').rstrip('=')


def _b64url_decode(value: str) -> bytes:
    padded = value + '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode('utf-8'))


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def create_jwt(payload: dict[str, Any], secret: str, exp_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=exp_minutes)

    header = {'alg': 'HS256', 'typ': 'JWT'}
    body = {
        **payload,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
    }

    header_part = _b64url_encode(_json_bytes(header))
    payload_part = _b64url_encode(_json_bytes(body))
    signing_input = f'{header_part}.{payload_part}'

    signature = hmac.new(
        secret.encode('utf-8'),
        signing_input.encode('utf-8'),
        hashlib.sha256,
    ).digest()

    signature_part = _b64url_encode(signature)
    return f'{signing_input}.{signature_part}'


def decode_jwt(token: str, secret: str) -> dict[str, Any] | None:
    try:
        header_part, payload_part, signature_part = token.split('.')
    except ValueError:
        return None

    signing_input = f'{header_part}.{payload_part}'
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        signing_input.encode('utf-8'),
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected_signature, actual_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_part).decode('utf-8'))
    except (ValueError, json.JSONDecodeError):
        return None

    exp = payload.get('exp')
    if not isinstance(exp, int):
        return None
    now = int(datetime.now(timezone.utc).timestamp())
    if exp <= now:
        return None

    return payload
