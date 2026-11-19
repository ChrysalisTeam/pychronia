"""
Overrides shared by the PROD settings of both sites (prod_cms.py and prod_game.py).

Deployment-specific values come from environment variables, or from the untracked ".env.<site>" and ".env" files at
the root of the repository (see ".env.example"), which the prod_*.py modules load BEFORE importing this one; a missing
required value raises ImproperlyConfigured.
"""

import os

import django

from config.settings._env import env

DEBUG = False

SITE_ID = env.int("SITE_ID", default=1)
SECRET_KEY = env.str("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # eg. "mydomain.com,www.mydomain.com"
SITE_DOMAIN = env.str("SITE_DOMAIN")  # eg. "https://mydomain.com", no final "/"
SESSION_COOKIE_DOMAIN = env.str("SESSION_COOKIE_DOMAIN", default=None)  # eg. ".mydomain.com"

# Django checks the Origin header of POST requests against these, in addition to the requested host
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_DOMAIN])

if env.bool("BEHIND_TLS_PROXY", default=False):
    # only if a reverse proxy terminates HTTPS and forwards plain HTTP requests (with this header) to Django
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if "MEDIA_ROOT" in os.environ:
    MEDIA_ROOT = env.str("MEDIA_ROOT")  # uploaded files, generated docs...
if "STATIC_ROOT" in os.environ:
    STATIC_ROOT = env.str("STATIC_ROOT")  # target of "collectstatic"

if "CACHE_URL" in os.environ:
    CACHES = {"default": env.cache_url("CACHE_URL")}  # eg. "pymemcache://127.0.0.1:11211?key_prefix=myprefix"

## EMAILS ##

SERVER_EMAIL = DEFAULT_FROM_EMAIL = BUG_REPORT_EMAIL = env.str("SERVER_EMAIL")
_admin_emails = env.list("ADMIN_EMAILS", default=[SERVER_EMAIL])  # they receive error reports
# Django 6.0 deprecated the (name, email) tuples of these settings
ADMINS = MANAGERS = _admin_emails if django.VERSION >= (6, 0) else [("", email) for email in _admin_emails]

_email_config = env.email_url("EMAIL_URL", default="smtp://localhost:25")  # eg. "smtp+tls://user:password@host:587"
EMAIL_BACKEND = _email_config["EMAIL_BACKEND"]
EMAIL_HOST = _email_config["EMAIL_HOST"]
EMAIL_PORT = _email_config["EMAIL_PORT"]
EMAIL_HOST_USER = _email_config["EMAIL_HOST_USER"] or ""
EMAIL_HOST_PASSWORD = _email_config["EMAIL_HOST_PASSWORD"] or ""
EMAIL_USE_TLS = _email_config.get("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = _email_config.get("EMAIL_USE_SSL", False)
EMAIL_SUBJECT_PREFIX = ""
