"""
This file is an alternative to let the web server communicate with Django during deployment.
"""
import os

from django.core.wsgi import get_wsgi_application

# Tell Django which settings file to load
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# The WSGI application object that the server uses to communicate
application = get_wsgi_application()
