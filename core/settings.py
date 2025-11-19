import os
from pathlib import Path
import environ
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()

# ── cargar .env según ENV
ENV = os.getenv("ENV", "development")
environ.Env.read_env(BASE_DIR / f".env.{ENV}")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # terceros
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "channels",
    "drf_spectacular",  # OpenAPI
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "dj_rest_auth",
    # apps propias
    "apps.users",
    "apps.authcodes",
    "apps.catalog",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # si querés plantillas propias, crea la carpeta "templates" en la raíz
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,  # busca templates dentro de cada app (admin incluido)
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"  # Channels listo

# ── DB y pooling estilo Supabase
DATABASES = {"default": env.db("DATABASE_URL")}
CONN_MAX_AGE = env.int("CONN_MAX_AGE", default=0)
DISABLE_SERVER_SIDE_CURSORS = env.bool("DISABLE_SERVER_SIDE_CURSORS", default=True)

# Cache (Redis) -> DRF throttling/otros
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="core"),
    }
}

LANGUAGE_CODE = "es"
TIME_ZONE = env("TIME_ZONE", default="America/Argentina/Buenos_Aires")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Opcional (deploy):
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ("v1", "v2"),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "120/min",
        "request_code": "5/min",  # usado por RequestCodeThrottle
    },
}

# OpenAPI
SPECTACULAR_SETTINGS = {
    "TITLE": env("OPENAPI_TITLE", default="API"),
    "DESCRIPTION": "API schema",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


# SimpleJWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# ── Users / allauth / dj-rest-auth
AUTH_USER_MODEL = "users.User"
SITE_ID = int(env("SITE_ID", default=1))

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# 🔹 Fallback que usará /api/v1/auth/google/login/ si no mandás ?next=
FRONTEND_LOGIN_REDIRECT_URL = env(
    "FRONTEND_LOGIN_REDIRECT_URL",
    default="http://localhost:5173/mi-cuenta",
)

# Django (no afecta al flujo OAuth de la opción B)
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# URLs del front a las que permitís volver
ACCOUNT_ALLOWED_REDIRECT_URLS = env.list(
    "ACCOUNT_ALLOWED_REDIRECT_URLS",
    default=[
        "http://localhost:5173/mi-cuenta",
        "http://localhost:5173/auth/callback",
    ],
)

# Nueva API de allauth (sin username)
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_ENABLED = False
ACCOUNT_SIGNUP_FIELDS = ["email*"]

# Evita la pantalla intermedia de allauth: va directo a Google
SOCIALACCOUNT_LOGIN_ON_GET = True

# Proveedor Google (credenciales desde .env)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["openid", "email", "profile"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}

# (Opcional) si creaste el adapter para permitir alta solo por social:
SOCIALACCOUNT_ADAPTER = "apps.users.adapters.SocialOnlySignupAdapter"

# dj-rest-auth con JWT
REST_AUTH = {
    "USE_JWT": True,
    "TOKEN_MODEL": None,
}

# Email
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@example.com")

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool(
    "CELERY_TASK_ALWAYS_EAGER", default=False
)  # True en tests si quieres
CELERY_TASK_EAGER_PROPAGATES = True

# Sentry (silencioso si no hay DSN)
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=env("SENTRY_DSN", default=None),
        environment=ENV,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        send_default_pii=False,
        enable_tracing=env.bool("SENTRY_ENABLE_TRACING", default=False),
    )
except Exception:
    pass

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
