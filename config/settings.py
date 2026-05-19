import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'your-django-core-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']  # Restrict this appropriately in live production environments

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Structural Extensions
    'corsheaders',
    # App
    'booking',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Handles cross-origin requests
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# Allow your local React frontend port to securely complete API operations
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

# Paystack API Keys (Store these safely in an environment file later)
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_your_secret_key_here')

WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# Ensure Django has a standard SQLite layout target configured to write to
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Tells Django how to handle automatic model index increments safely
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- STATIC FILES CONFIGURATION ---
# The URL path used to access static files in the browser (Must have leading and trailing slashes)
STATIC_URL = '/static/'

# Tells Django where to look for global static files during development
STATICFILES_DIRS = []

# The physical directory where Django will collect ALL static assets for production deployment
STATIC_ROOT = BASE_DIR / 'staticfiles'

# settings.py

# --- GOOGLE EMAIL SERVER INFRASTRUCTURE ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'zainaabahmed05@gmail.com'  # Your organizer email address
EMAIL_HOST_PASSWORD = 'your-google-app-password-here'  # 16-character code from Google Security
DEFAULT_FROM_EMAIL = f"Zainab Ahmed <{EMAIL_HOST_USER}>"

# --- PAYSTACK MERCHANDISE KEYS ---
PAYSTACK_SECRET_KEY = 'sk_live_your_actual_live_secret_key_here'