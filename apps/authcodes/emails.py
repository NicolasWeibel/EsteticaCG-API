# ==========================================
# apps/authcodes/emails.py
# ==========================================
from django.core.mail import send_mail
from django.conf import settings


def send_login_code(email: str, code: str):
    subject = "Tu código de acceso"
    body = f"Usa este código para iniciar sesión: {code}\nExpira en 10 minutos."
    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [email],
        fail_silently=False,
    )
