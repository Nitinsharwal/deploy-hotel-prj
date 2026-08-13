import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

load_dotenv(override=True)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set. Add it to your .env file or environment variables.")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

_default_hosts = "localhost,127.0.0.1" if DEBUG else ""
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", _default_hosts).split(",") if host.strip()
]
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set when DEBUG=False.")

# CSRF trusted origins (full scheme+host) — required for HTTPS POSTs on Vercel/Render etc.
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]


# Application definition

INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # required by allauth
    "django.contrib.sitemaps",  # /sitemap.xml
    "axes",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "cloudinary_storage",
    "cloudinary",
    "hotel_app",
    "accounts",
]

if DEBUG:
    try:
        import debug_toolbar  # noqa: F401
        INSTALLED_APPS.append("debug_toolbar")
    except ImportError:
        pass

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "hotel_app.middleware.MediaCacheMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "axes.middleware.AxesMiddleware",
]

if DEBUG and "debug_toolbar" in INSTALLED_APPS:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS = ["127.0.0.1"]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AXES_ENABLED = os.getenv("AXES_ENABLED", "True").lower() == "true"
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_RESET_ON_SUCCESS = True

ROOT_URLCONF = "hotel_prj.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "accounts" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Injects `hb_ctx` (chatbot auto-fill) into every template
                # render. Cheap: returns immediately for anonymous users;
                # one indexed SELECT for logged-in users.
                "accounts.context_processors.chatbot_context",
            ],
        },
    },
]

WSGI_APPLICATION = "hotel_prj.wsgi.application"

def _getenv(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _postgres_config_from_url(database_url):
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        return None

    name = parsed.path.lstrip("/")
    if not name:
        return None

    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or "5432"),
    }

    options = {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}
    if options:
        config["OPTIONS"] = options

    return config


def _database_config_from_env():
    database_url = _getenv("DATABASE_URL", "POSTGRES_URL", "POSTGRESQL_URL")
    if database_url:
        config = _postgres_config_from_url(database_url)
        if config:
            return {"default": config}

    # Legacy MYSQL_* names are still accepted during the transition so existing
    # deployments keep working until the environment variables are renamed.
    host = _getenv("POSTGRES_HOST", "PGHOST", "MYSQL_HOST")
    if host:
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _getenv(
                "POSTGRES_DB",
                "POSTGRES_DATABASE",
                "PGDATABASE",
                "MYSQL_DATABASE",
                default="postgres",
            ),
            "USER": _getenv("POSTGRES_USER", "PGUSER", "MYSQL_USER", default="postgres"),
            "PASSWORD": _getenv("POSTGRES_PASSWORD", "PGPASSWORD", "MYSQL_PASSWORD", default=""),
            "HOST": host,
            "PORT": _getenv("POSTGRES_PORT", "PGPORT", "MYSQL_PORT", default="5432"),
        }

        sslmode = _getenv("POSTGRES_SSLMODE", "PGSSLMODE")
        if sslmode:
            config["OPTIONS"] = {"sslmode": sslmode}

        return {"default": config}

    # SQLite fallback is for local dev only. In production we refuse to start
    # without an explicit DATABASE_URL to avoid silently writing to an ephemeral file.
    if not DEBUG:
        raise RuntimeError(
            "No DATABASE_URL / POSTGRES_* env vars set. "
            "Refusing to fall back to SQLite when DEBUG=False."
        )
    return {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


DATABASES = _database_config_from_env()

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"

STATICFILES_DIRS = [BASE_DIR / "hotel_app/static"]


STATIC_ROOT = BASE_DIR / "staticfiles"

# Computed once so the same string is used in BOTH branches (legacy
# STATICFILES_STORAGE setting OR new STORAGES dict). Django 4.2+ accepts
# either — but NEVER both in the same settings module, or it raises
# ImproperlyConfigured("STATICFILES_STORAGE/STORAGES are mutually exclusive").
_staticfiles_backend = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedStaticFilesStorage"
)

WHITENOISE_MAX_AGE = 60 * 60  # 1 hour
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

MEDIA_CACHE_MAX_AGE = 60 * 60 * 24  # 1 day

# Cloud media storage (Cloudinary) — env-gated.
# When CLOUDINARY_CLOUD_NAME is set, switch to the new STORAGES dict syntax
# (Django 4.2+) so we can wire BOTH the media backend (Cloudinary) and the
# staticfiles backend (WhiteNoise in prod / vanilla in dev) at once.
# When it's empty, fall back to the legacy STATICFILES_STORAGE single-string
# setting — simpler, works fine for local dev.
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
if CLOUDINARY_CLOUD_NAME:
    STORAGES = {
        "default": {
            # Every FileField (.image, .profile_image, etc.) uploads to
            # Cloudinary and returns a CDN URL on `.url`.
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            # Static (CSS/JS) stays on WhiteNoise — baked into the deploy by
            # `collectstatic`, no benefit from putting it in Cloudinary.
            "BACKEND": _staticfiles_backend,
        },
    }
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
        "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
        # Force https:// URLs in templates — without this, the SDK sometimes
        # emits http:// which gets mixed-content-blocked on HTTPS pages.
        "SECURE": True,
    }
else:
    # Cloudinary OFF (local dev, tests). Use the legacy single-string setting.
    # NOTE: defining STATICFILES_STORAGE here only — never alongside STORAGES —
    # is what avoids the "mutually exclusive" error.
    STATICFILES_STORAGE = _staticfiles_backend
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

host_user = os.getenv("EMAIL_USER")
host_pass = os.getenv("EMAIL_PASSWORD")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", host_user or "noreply@example.com")

if RESEND_API_KEY:
    EMAIL_BACKEND = "hotel_prj.email_backend.ResendEmailBackend"
elif host_user and host_pass:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = host_user
EMAIL_HOST_PASSWORD = host_pass
EMAIL_TIMEOUT = 10

_redis_url = os.getenv("REDIS_URL", "")
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
            "TIMEOUT": 300, 
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "noma-default",
            "TIMEOUT": 300,
        }
    }


ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_REQUIRED = True 
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # Google's email is already verified
ACCOUNT_USERNAME_REQUIRED = False  # use email as username
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True  # one-click Google button (no confirm screen)
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_ADAPTER = "accounts.adapters.AutoConnectByEmailAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
RAZORPAY_CURRENCY = os.getenv("RAZORPAY_CURRENCY", "INR")
# Public site URL for building redirect targets after payment.
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")


if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days; bump to 1y once verified stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
