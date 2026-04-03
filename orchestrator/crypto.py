"""租户密钥加解密 — Fernet 对称加密"""

import os
import logging
from cryptography.fernet import Fernet

log = logging.getLogger("infohub.crypto")

_KEY = os.environ.get("ENCRYPTION_KEY", "")


def _get_fernet() -> Fernet:
    if not _KEY:
        raise RuntimeError("ENCRYPTION_KEY 环境变量未设置")
    return Fernet(_KEY.encode() if isinstance(_KEY, str) else _KEY)


# 模块加载时验证 ENCRYPTION_KEY 格式（如果已设置）
if _KEY:
    try:
        _get_fernet()
    except Exception as e:
        log.critical(f"ENCRYPTION_KEY 格式无效: {e}")
        raise RuntimeError(f"ENCRYPTION_KEY 格式无效: {e}")


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """生成新的 Fernet key（部署时用一次）"""
    return Fernet.generate_key().decode()
