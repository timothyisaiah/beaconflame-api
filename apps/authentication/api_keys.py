import hashlib
import hmac
from functools import lru_cache

from django.conf import settings


def hash_api_key(raw_key: str) -> str:
    pepper = settings.API_KEY_PEPPER.encode()
    return hmac.new(pepper, raw_key.encode(), hashlib.sha256).hexdigest()


def verify_api_key(raw_key: str, hashed: str) -> bool:
    expected = hash_api_key(raw_key)
    return hmac.compare_digest(expected, hashed)


def extract_prefix(raw_key: str, length: int = 16) -> str:
    return raw_key[:length] if len(raw_key) >= length else raw_key
