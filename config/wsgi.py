import os

from django.core.wsgi import get_wsgi_application

# Directs Django to use your settings configuration profiles
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Instantiates the core application gateway variable the web server is looking for
application = get_wsgi_application()