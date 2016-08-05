from __future__ import absolute_import, unicode_literals

import os


def setup():
    try:
        os.environ['DJANGO_SETTINGS_MODULE']
    except KeyError:
        raise RuntimeError("Use: setup.py test or testproj/manage.py test")
