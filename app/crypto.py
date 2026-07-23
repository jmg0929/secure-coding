"""민감 정보(계좌번호) 암호화.

AES-256-GCM 사용:
  - 기밀성 + 무결성(인증 태그)을 동시에 제공한다. 암호문이 변조되면 복호화가 실패한다.
  - 매 암호화마다 12바이트 nonce 를 새로 생성한다. (nonce 재사용은 GCM 에서 치명적)

키 관리:
  - ACCOUNT_ENC_KEY 환경변수(hex 64자 = 32바이트)를 최우선으로 사용한다.
  - 없으면 SECRET_KEY 로부터 HKDF 로 **용도 분리된** 키를 파생한다.
    (세션 서명 키와 암호화 키를 그대로 공유하지 않기 위함)
  - 실제 운영에서는 KMS/Vault 등으로 관리하고 정기 교체하는 것이 바람직하다.
"""
import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

NONCE_SIZE = 12
_INFO = b"secondhand-market:account-number:v1"


class DecryptError(Exception):
    """복호화 실패(키 불일치 또는 암호문 변조)."""


def derive_key(config) -> bytes:
    """설정에서 32바이트 암호화 키를 얻는다."""
    explicit = config.get("ACCOUNT_ENC_KEY")
    if explicit:
        try:
            key = bytes.fromhex(explicit)
        except ValueError as e:
            raise RuntimeError("ACCOUNT_ENC_KEY 는 hex 문자열이어야 합니다.") from e
        if len(key) != 32:
            raise RuntimeError("ACCOUNT_ENC_KEY 는 32바이트(hex 64자)여야 합니다.")
        return key

    # 폴백: SECRET_KEY 에서 용도 분리(HKDF)해 파생
    secret = config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY 가 없어 암호화 키를 만들 수 없습니다.")
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO
    ).derive(secret)


def encrypt(plaintext: str, key: bytes) -> str:
    """평문 → base64(nonce || 암호문+태그)."""
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be str")
    nonce = os.urandom(NONCE_SIZE)          # 매번 새로 생성
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str, key: bytes) -> str:
    """base64(nonce || 암호문) → 평문. 변조 시 DecryptError."""
    try:
        raw = base64.b64decode(token.encode("ascii"))
        nonce, ct = raw[:NONCE_SIZE], raw[NONCE_SIZE:]
        return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:  # InvalidTag, binascii.Error 등
        raise DecryptError("계좌 정보를 복호화할 수 없습니다.") from e
