from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from .config import load_settings


def _local_master_key() -> bytes:
    settings = load_settings()
    if not settings.kms_master_key:
        raise HTTPException(status_code=503, detail="Local KMS provider requires MEMORYOS_ENTERPRISE_LOCAL_KMS_MASTER_KEY.")
    raw = settings.kms_master_key.strip()
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def generate_data_key() -> tuple[bytes, str, str]:
    settings = load_settings()
    if settings.kms_provider == "aws":
        try:
            import boto3
        except Exception as exc:
            raise HTTPException(status_code=503, detail="AWS KMS provider requires boto3.") from exc
        kwargs = {"region_name": settings.kms_region} if settings.kms_region else {}
        response = boto3.client("kms", **kwargs).generate_data_key(KeyId=settings.kms_key_id, KeySpec="AES_256")
        return bytes(response["Plaintext"]), base64.urlsafe_b64encode(bytes(response["CiphertextBlob"])).decode("ascii"), ""
    if settings.kms_provider != "local":
        raise HTTPException(status_code=503, detail=f"Unsupported KMS provider: {settings.kms_provider}")
    dek = os.urandom(32)
    nonce = os.urandom(12)
    encrypted_dek = AESGCM(_local_master_key()).encrypt(nonce, dek, settings.kms_key_id.encode("utf-8"))
    return dek, base64.urlsafe_b64encode(encrypted_dek).decode("ascii"), base64.urlsafe_b64encode(nonce).decode("ascii")


def decrypt_data_key(encrypted_dek: str, dek_nonce: str, kms_key_id: str) -> bytes:
    settings = load_settings()
    if settings.kms_provider == "aws":
        try:
            import boto3
        except Exception as exc:
            raise HTTPException(status_code=503, detail="AWS KMS provider requires boto3.") from exc
        kwargs = {"region_name": settings.kms_region} if settings.kms_region else {}
        response = boto3.client("kms", **kwargs).decrypt(CiphertextBlob=base64.urlsafe_b64decode(encrypted_dek))
        return bytes(response["Plaintext"])
    if settings.kms_provider != "local":
        raise HTTPException(status_code=503, detail=f"Unsupported KMS provider: {settings.kms_provider}")
    return AESGCM(_local_master_key()).decrypt(
        base64.urlsafe_b64decode(dek_nonce),
        base64.urlsafe_b64decode(encrypted_dek),
        kms_key_id.encode("utf-8"),
    )
