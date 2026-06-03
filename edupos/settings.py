from pathlib import Path
import os
import environ
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Variables de entorno ─────────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    DEBUG_TOOLBAR_ENABLED=(bool, True),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1', '192.168.1.9']),
)
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY   = env('SECRET_KEY')
DEBUG        = env('DEBUG')
DEBUG_TOOLBAR_ENABLED = env('DEBUG_TOOLBAR_ENABLED')
ALLOWED_HOSTS = env('ALLOWED_HOSTS') + ['.railway.app']

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['http://localhost', 'http://127.0.0.1', 'https://cohesive-salutary-irritable.ngrok-free.dev']
)

# ─── Cloudinary ──────────────────────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY':    env('CLOUDINARY_API_KEY',    default=''),
    'API_SECRET': env('CLOUDINARY_API_SECRET', default=''),
}

# ─── Aplicaciones ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Librerías de terceros
    'cloudinary',
    'cloudinary_storage',
    'axes',
    'simple_history',
    'csp',
    'widget_tweaks',
    # Allauth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Apps propias
    'core',
    'authentication',
    'app_admin',
    'app_estudiante',
    'app_padre',
    'app_docente',
    'app_empleado',
    'pagos',
]
SITE_ID = 1

if DEBUG and env('DEBUG_TOOLBAR_ENABLED'):
    INSTALLED_APPS += ['debug_toolbar']

# ─── Autenticación ────────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/'
LOGOUT_REDIRECT_URL = '/'

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'axes.middleware.AxesMiddleware',   # ← al final para no interferir con allauth
]

if DEBUG and env('DEBUG_TOOLBAR_ENABLED'):
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

ROOT_URLCONF = 'edupos.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'edupos.wsgi.application'

# ─── Base de datos ────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL and DATABASE_URL.startswith(('postgres', 'postgresql', 'mysql', 'sqlite')):
    DATABASES = {'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

# ─── Validadores de contraseña ────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internacionalización ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'es-co'
TIME_ZONE     = 'America/Bogota'
USE_I18N      = True
USE_TZ        = True

# ─── Archivos estáticos y media ───────────────────────────────────────────────
STATIC_URL    = '/static/'
STATIC_ROOT   = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL     = '/media/'
MEDIA_ROOT    = BASE_DIR / 'media'

_use_cloudinary = bool(CLOUDINARY_STORAGE.get('CLOUD_NAME') and CLOUDINARY_STORAGE.get('API_KEY'))

STORAGES = {
    'default': {
        'BACKEND': (
            'cloudinary_storage.storage.MediaCloudinaryStorage'
            if _use_cloudinary
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Caché ────────────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'edupos-cache',
    }
}


# ─── django-axes ──────────────────────────────────────────────────────────────
AXES_ENABLED          = False   # ← temporal para diagnóstico
AXES_FAILURE_LIMIT    = 5
AXES_COOLOFF_TIME     = 1
AXES_LOCKOUT_CALLABLE = None
AXES_RESET_ON_SUCCESS = True
AXES_NEVER_LOCKOUT_WHITELIST = True
AXES_IP_WHITELIST     = ['127.0.0.1']

# ─── django-csp ───────────────────────────────────────────────────────────────
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            "'unsafe-inline'",
            'cdn.jsdelivr.net',
            'cdnjs.cloudflare.com',
            'cdn.skypack.dev',
        ),
        'style-src': (
            "'self'",
            "'unsafe-inline'",
            'fonts.googleapis.com',
            'cdn.jsdelivr.net',
            'cdnjs.cloudflare.com',
        ),
        'font-src': (
            "'self'",
            'fonts.gstatic.com',
            'cdn.jsdelivr.net',
        ),
        'img-src': ("'self'", 'data:', 'blob:', 'res.cloudinary.com'),
        'connect-src': ("'self'",),
        'frame-ancestors': ("'none'",),
    }
}

# ─── django-debug-toolbar ────────────────────────────────────────────────────
if DEBUG:
    INTERNAL_IPS = ['127.0.0.1']

# ─── django-simple-history ────────────────────────────────────────────────────
SIMPLE_HISTORY_REVERT_DISABLED = False

# ─── Logging estructurado con structlog ──────────────────────────────────────
import structlog

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'edupos': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# ─── django-allauth ───────────────────────────────────────────────────────────
ACCOUNT_LOGIN_METHODS           = {'email'}      # allauth v65+: reemplaza ACCOUNT_AUTHENTICATION_METHOD
ACCOUNT_EMAIL_REQUIRED          = True
ACCOUNT_USERNAME_REQUIRED       = False
ACCOUNT_EMAIL_VERIFICATION      = 'none'
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False
SOCIALACCOUNT_AUTO_SIGNUP       = True
SOCIALACCOUNT_LOGIN_ON_GET      = True
SOCIALACCOUNT_ADAPTER           = 'authentication.adapters.RolSocialAccountAdapter'
ACCOUNT_ADAPTER                 = 'allauth.account.adapter.DefaultAccountAdapter'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account consent',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}
# ─── Google Calendar API ─────────────────────────────────────────────────────
# Reutiliza las mismas credenciales OAuth del login social (allauth)
GOOGLE_CLIENT_ID     = env('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = env('GOOGLE_SECRET', default='')

# ─── Proxy SSL (ngrok en dev, Railway en prod) ───────────────────────────────
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ─── MercadoPago ─────────────────────────────────────────────────────────────
MERCADOPAGO_ACCESS_TOKEN  = env('MERCADOPAGO_ACCESS_TOKEN',  default='')
MERCADOPAGO_WEBHOOK_SECRET = env('MERCADOPAGO_WEBHOOK_SECRET', default='')
SITE_URL = env('SITE_URL', default='http://127.0.0.1:8000')