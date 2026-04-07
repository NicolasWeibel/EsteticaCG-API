from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


CODE_EXPIRES_MINUTES = 10


def _from_email() -> str:
    return formataddr(
        (
            getattr(settings, "EMAIL_FROM_NAME", ""),
            getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        )
    )


def _send_code_email(
    *,
    email: str,
    code: str,
    subject: str,
    eyebrow: str,
    title: str,
    intro_action: str,
):
    context = {
        "brand_name": getattr(settings, "EMAIL_FROM_NAME", "Estetica CG"),
        "code": code,
        "expires_minutes": CODE_EXPIRES_MINUTES,
        "eyebrow": eyebrow,
        "title": title,
        "intro_action": intro_action,
    }

    text_body = render_to_string("emails/otp_code.txt", context)
    html_body = render_to_string("emails/otp_code.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=_from_email(),
        to=[email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_login_code(email: str, code: str):
    _send_code_email(
        email=email,
        code=code,
        subject="Tu codigo de acceso",
        eyebrow="Codigo de acceso",
        title="Tu codigo de acceso",
        intro_action="completar tu inicio de sesion",
    )


def send_verification_code(email: str, code: str):
    _send_code_email(
        email=email,
        code=code,
        subject="Tu codigo de verificacion",
        eyebrow="Codigo de verificacion",
        title="Tu codigo de verificacion",
        intro_action="verificar tu identidad",
    )
