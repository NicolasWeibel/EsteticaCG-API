# ===============================
# apps/authcodes/models.py  (OTP hasheado)
# ===============================
from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets, hashlib, hmac


def _hash_code(code: str, salt: str) -> str:
    # Por qué: evitar guardar el OTP en texto plano
    return hashlib.sha256(f"{salt}{code}".encode("utf-8")).hexdigest()


class OTPLoginCode(models.Model):
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=64, db_index=True)
    salt = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    ip = models.GenericIPAddressField(null=True, blank=True)

    @classmethod
    def create_fresh(cls, email: str, ip: str | None = None, ttl_minutes: int = 10):
        from random import randint

        raw_code = f"{randint(0, 999_999):06d}"
        salt = secrets.token_hex(16)
        code_hash = _hash_code(raw_code, salt)
        obj = cls.objects.create(
            email=email,
            code_hash=code_hash,
            salt=salt,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
            ip=ip,
        )
        return obj, raw_code  # devolvemos el código para enviarlo por email

    def verify(self, raw_code: str) -> bool:
        expected = _hash_code(raw_code, self.salt)
        return (
            (not self.is_used)
            and (self.expires_at >= timezone.now())
            and hmac.compare_digest(self.code_hash, expected)
        )

    def __str__(self):
        return f"{self.email} • used={self.is_used}"
