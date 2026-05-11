from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from .config import load_settings
from .kms import decrypt_data_key, generate_data_key


def encrypt_text(plaintext: str, aad: str) -> dict[str, str]:
    settings = load_settings()
    if not settings.encryption_enabled:
        return {}
    dek, encrypted_dek, dek_nonce = generate_data_key()
    content_nonce = os.urandom(12)
    content_ciphertext = AESGCM(dek).encrypt(content_nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    return {
        "ciphertext": base64.urlsafe_b64encode(content_ciphertext).decode("ascii"),
        "content_nonce": base64.urlsafe_b64encode(content_nonce).decode("ascii"),
        "encrypted_dek": encrypted_dek,
        "dek_nonce": dek_nonce,
        "kms_key_id": settings.kms_key_id,
    }


def decrypt_text(
    fallback: str,
    *,
    ciphertext: Optional[str],
    content_nonce: Optional[str],
    encrypted_dek: Optional[str],
    dek_nonce: Optional[str],
    kms_key_id: Optional[str],
    aad: str,
) -> str:
    if not ciphertext or not content_nonce or not encrypted_dek or dek_nonce is None or not kms_key_id:
        return fallback
    dek = decrypt_data_key(encrypted_dek, dek_nonce, kms_key_id)
    plaintext = AESGCM(dek).decrypt(
        base64.urlsafe_b64decode(content_nonce),
        base64.urlsafe_b64decode(ciphertext),
        aad.encode("utf-8"),
    )
    return plaintext.decode("utf-8")
