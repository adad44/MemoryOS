from __future__ import annotations

import hashlib
import hmac
import re

from fastapi import HTTPException

from .config import load_settings


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-]{1,}", re.IGNORECASE)


def terms_for_text(text: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for match in TOKEN_RE.findall(text.lower()):
        if match not in seen:
            seen.add(match)
            terms.append(match)
    return terms


def term_hash(term: str) -> str:
    settings = load_settings()
    key = settings.search_index_key
    if settings.encryption_enabled and not key:
        raise HTTPException(status_code=503, detail="Encrypted search requires MEMORYOS_ENTERPRISE_SEARCH_INDEX_KEY.")
    if not key:
        key = "memoryos-enterprise-dev-search"
    return hmac.new(hashlib.sha256(key.encode("utf-8")).digest(), term.lower().encode("utf-8"), hashlib.sha256).hexdigest()


def term_hashes_for_text(text: str) -> list[str]:
    return [term_hash(term) for term in terms_for_text(text)]
