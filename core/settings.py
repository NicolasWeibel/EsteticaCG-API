import os
from pathlib import Path
import environ
from datetime import timedelta
from core.csrf import validate_cookie_settings

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()


def _env_pattern_list(name: str) -> list[str]:
    raw = env(name, default="")
    if not raw:
        return []
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def _env_prefix_list(name: str) -> list[str]:
    raw = env(name, default="")
    if not raw:
        return []
    return [item.strip() for item in str(raw).split(";") if item.strip()]


# ── CARGAR .ENV (SEGÚN ENTORNO) ──
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
    "cloudinary_storage",
    "cloudinary",  # SDK general
    "django.contrib.sites",
    # Terceros
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "channels",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "dj_rest_auth",
    # Apps propias
    "apps.users",
    "apps.authcodes",
    "apps.catalog",
    "apps.scheduling",
    "apps.waxing",
    "apps.reviews",
]

MIDDLEWARE = [
    "core.middleware.HealthzShortCircuitMiddleware",
    "core.middleware.ProxySecretMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # 👈 Vital para el CSS en Cloud Run
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.LanAwareCsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ── CORS Y SEGURIDAD ──
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = _env_pattern_list("CORS_ALLOWED_ORIGIN_REGEXES")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGIN_REGEXES = _env_pattern_list("CSRF_TRUSTED_ORIGIN_REGEXES")
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=False)
REQUIRE_PROXY_SECRET = env.bool("REQUIRE_PROXY_SECRET", default=False)
PROXY_SHARED_SECRET = env("PROXY_SHARED_SECRET", default="")
PROXY_SECRET_EXEMPT_PATH_PREFIXES = _env_prefix_list(
    "PROXY_SECRET_EXEMPT_PATH_PREFIXES"
) or [
    "/healthz",
    "/accounts/",
    "/api/v1/auth/google/",
]

# Permitir cookies en entornos cruzados (Localhost <-> Cloud Run)
# En HTTP local Chrome bloquea "SameSite=None" sin "Secure", por eso usamos "Lax" en DEBUG.
SESSION_COOKIE_SAMESITE = env(
    "SESSION_COOKIE_SAMESITE",
    default="Lax" if DEBUG else "None",
)
CSRF_COOKIE_SAMESITE = env(
    "CSRF_COOKIE_SAMESITE",
    default="Lax" if DEBUG else "None",
)

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
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
ASGI_APPLICATION = "core.asgi.application"

# ── BASE DE DATOS ──
DATABASES = {"default": env.db("DATABASE_URL")}
CONN_MAX_AGE = env.int("CONN_MAX_AGE", default=0)
DISABLE_SERVER_SIDE_CURSORS = env.bool("DISABLE_SERVER_SIDE_CURSORS", default=True)

# ── CACHÉ (REDIS O MEMORIA) ──
REDIS_URL = os.getenv("REDIS_URL", None)
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="core"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

LANGUAGE_CODE = "es"
TIME_ZONE = env("TIME_ZONE", default="America/Argentina/Buenos_Aires")
USE_I18N = True
USE_TZ = True

# ── ARCHIVOS ESTÁTICOS (CSS/JS) ──
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ── ARCHIVOS MEDIA (Imágenes) ──
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Configuración unificada de Almacenamiento (Django 4.2+)
STORAGES = {
    "default": {
        "BACKEND": "apps.catalog.storage.AutoMediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Si estamos en Producción (DEBUG=False), usamos WhiteNoise para los estáticos
if not DEBUG:
    STORAGES["staticfiles"][
        "BACKEND"
    ] = "whitenoise.storage.CompressedStaticFilesStorage"

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME", default=""),
    "API_KEY": env("CLOUDINARY_API_KEY", default=""),
    "API_SECRET": env("CLOUDINARY_API_SECRET", default=""),
    "RESOURCE_TYPE": env("CLOUDINARY_RESOURCE_TYPE", default="auto"),
    "MEDIA_TAG": env("CLOUDINARY_FOLDER", default="estetica-general"),
    "PREFIX": env("CLOUDINARY_FOLDER", default="estetica-general"),
}


# ── DRF ──
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("core.authentication.CookieJWTAuthentication",),
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
        "request_code": "5/min",
    },
}

# ── OPENAPI ──
SPECTACULAR_SETTINGS = {
    "TITLE": env("OPENAPI_TITLE", default="API"),
    "DESCRIPTION": "API schema",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ── JWT ──
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

AUTH_COOKIE_ACCESS_NAME = env("AUTH_COOKIE_ACCESS_NAME", default="accessToken")
AUTH_COOKIE_REFRESH_NAME = env("AUTH_COOKIE_REFRESH_NAME", default="refreshToken")
AUTH_COOKIE_PATH = env("AUTH_COOKIE_PATH", default="/")
AUTH_COOKIE_DOMAIN = env("AUTH_COOKIE_DOMAIN", default="").strip() or None
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=not DEBUG)
AUTH_COOKIE_SAMESITE = env(
    "AUTH_COOKIE_SAMESITE",
    default="Lax" if DEBUG else "Strict",
)
validate_cookie_settings(AUTH_COOKIE_SAMESITE, AUTH_COOKIE_SECURE)

# ── AUTH & ALLAUTH ──
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
ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES = _env_pattern_list(
    "ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES",
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

# ── EMAIL & CELERY ──
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_FROM_NAME = env("EMAIL_FROM_NAME", default="Estetica CG")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@example.com")

# Celery
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL", default=REDIS_URL if REDIS_URL else "memory://"
)
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    default=REDIS_URL if REDIS_URL else "db+sqlite:///results.sqlite",
)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_IGNORE_RESULT = env.bool("CELERY_TASK_IGNORE_RESULT", default=True)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True

# ── SENTRY ──
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
    )
except Exception:
    pass

# Seguridad HTTPS
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── REVIEWS (PUBLIC ENDPOINT + PROVIDERS) ──
REVIEWS_PROVIDER = env("REVIEWS_PROVIDER", default="manual")
REVIEWS_FALLBACK_TO_MANUAL = env.bool("REVIEWS_FALLBACK_TO_MANUAL", default=True)
REVIEWS_DEFAULT_MIN_RATING = env.int("REVIEWS_DEFAULT_MIN_RATING", default=4)
REVIEWS_DEFAULT_WITH_CONTENT = env.bool("REVIEWS_DEFAULT_WITH_CONTENT", default=True)
REVIEWS_PUBLIC_LIMIT = env.int("REVIEWS_PUBLIC_LIMIT", default=10)
REVIEWS_CACHE_DAYS = env.int("REVIEWS_CACHE_DAYS", default=7)
REVIEWS_CACHE_REFRESH_HOURS = env.int("REVIEWS_CACHE_REFRESH_HOURS", default=24)
REVIEWS_GOOGLE_AUTO_SYNC_ON_READ = env.bool(
    "REVIEWS_GOOGLE_AUTO_SYNC_ON_READ",
    default=True,
)
REVIEWS_GOOGLE_ACCOUNT_ID = env("REVIEWS_GOOGLE_ACCOUNT_ID", default="")
REVIEWS_GOOGLE_LOCATION_ID = env("REVIEWS_GOOGLE_LOCATION_ID", default="")
REVIEWS_GOOGLE_ACCESS_TOKEN = env("REVIEWS_GOOGLE_ACCESS_TOKEN", default="")
REVIEWS_GOOGLE_REFRESH_TOKEN = env("REVIEWS_GOOGLE_REFRESH_TOKEN", default="")
REVIEWS_GOOGLE_CLIENT_ID = env("REVIEWS_GOOGLE_CLIENT_ID", default="")
REVIEWS_GOOGLE_CLIENT_SECRET = env("REVIEWS_GOOGLE_CLIENT_SECRET", default="")


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}
