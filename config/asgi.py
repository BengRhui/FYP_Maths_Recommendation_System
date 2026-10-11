"""
This file is to let web server to communicate with Django during deployment.
"""

import os

from django.core.asgi import get_asgi_application

# Tell Django which settings file to load
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# The ASGI application object that the server uses to communicate
application = get_asgi_application()
