from django.core import mail
from django.test import override_settings

from apps.authcodes.emails import send_login_code, send_verification_code


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_FROM_NAME="ZondaLogic",
    DEFAULT_FROM_EMAIL="sender@example.com",
)
def test_send_login_code_renders_html_and_text():
    send_login_code("user@example.com", "123456")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]

    assert message.subject == "Tu codigo de acceso"
    assert message.to == ["user@example.com"]
    assert message.from_email == "ZondaLogic <sender@example.com>"
    assert "Codigo: 123456" in message.body
    assert "Expira en 10 minutos." in message.body
    assert len(message.alternatives) == 1
    assert message.alternatives[0].mimetype == "text/html"
    assert "Tu codigo de acceso" in message.alternatives[0].content
    assert "123456" in message.alternatives[0].content


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_FROM_NAME="ZondaLogic",
    DEFAULT_FROM_EMAIL="sender@example.com",
)
def test_send_verification_code_uses_verification_copy():
    send_verification_code("user@example.com", "654321")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]

    assert message.subject == "Tu codigo de verificacion"
    assert "verificar tu identidad" in message.body
    assert "654321" in message.alternatives[0].content
    assert "Tu codigo de verificacion" in message.alternatives[0].content
