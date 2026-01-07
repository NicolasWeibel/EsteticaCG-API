# ==========================================
# apps/authcodes/emails.py
# ==========================================
from django.core.mail import send_mail
from django.conf import settings


def send_login_code(email: str, code: str):
    subject = "Tu codigo de acceso"
    body = f"Usa este codigo para iniciar sesion: {code}\nExpira en 10 minutos."
    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [email],
        fail_silently=False,
    )


def send_verification_code(email: str, code: str):
    subject = "Tu codigo de verificacion"
    body = f"Usa este codigo para verificar tu identidad: {code}\nExpira en 10 minutos."
    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [email],
        fail_silently=False,
    )
