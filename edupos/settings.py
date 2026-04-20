from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Variables de entorno ─────────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY   = env('SECRET_KEY')
DEBUG        = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# ─── Aplicaciones ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Librerías de terceros
    'axes',
    'simple_history',
    'csp',
    'widget_tweaks',
    # Apps propias
    'core',
    'authentication',
    'app_admin',
    'app_estudiante',
    'app_padre',
    'app_docente',
]

if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # Archivos estáticos en producción
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',               # Protección contra fuerza bruta
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',  # Registra usuario en historial
]

if DEBUG:
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
DATABASES = {
    'default': env.db(default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

# ─── Validadores de contraseña ────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Autenticación ────────────────────────────────────────────────────────────
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/admin-panel/'
LOGOUT_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
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

# WhiteNoise: compresión gzip y caché headers para estáticos
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Caché (LocMemCache en desarrollo; cambiar a Redis en producción) ─────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'edupos-cache',
    }
}

# ─── django-axes (protección fuerza bruta en login) ──────────────────────────
AXES_FAILURE_LIMIT        = 5       # Bloquear tras 5 intentos fallidos
AXES_COOLOFF_TIME         = 1       # Bloqueo de 1 hora
AXES_LOCKOUT_CALLABLE     = None    # Usa la vista de lockout por defecto
AXES_RESET_ON_SUCCESS     = True    # Resetea contador al iniciar sesión bien

# ─── django-csp (Content Security Policy) ────────────────────────────────────
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            "'unsafe-inline'",           # Necesario para scripts inline en templates
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
        'img-src': ("'self'", 'data:', 'blob:'),
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
