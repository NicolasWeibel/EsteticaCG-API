# ===============================
# apps/authcodes/tasks.py  (Celery)
# ===============================
from celery import shared_task
from .emails import send_login_code, send_verification_code


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_login_code_task(self, email: str, code: str):
    # Por qué: enviar async y reintentar si el proveedor falla
    try:
        send_login_code(email, code)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_verification_code_task(self, email: str, code: str):
    try:
        send_verification_code(email, code)
    except Exception as exc:
        raise self.retry(exc=exc)
