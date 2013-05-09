VERSION = (0, 9, 0, 'beta', 1)


def get_version():
    try:
        from django.utils.version import get_version as django_get_version
    except  ImportError:
        from django import get_version as django_get_version
    return django_get_version(VERSION) # pragma: no cover
