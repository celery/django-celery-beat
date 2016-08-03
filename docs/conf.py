# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import os

from sphinx_celery import conf

globals().update(conf.build_config(
    'django-celery-beat', __file__,
    project='django_celery_beat',
    # version_dev='2.0',
    # version_stable='1.4',
    canonical_url='http://django-celery-beat.readthedocs.org',
    webdomain='',
    github_project='celery/django-celery-beat',
    copyright='2016',
    html_logo='images/logo.png',
    html_favicon='images/favicon.ico',
    html_prepend_sidebars=[],
    include_intersphinx={'python', 'sphinx'},
    # django_settings='testproj.settings',
    # path_additions=[os.path.join(os.pardir, 'testproj')],
    # apicheck_ignore_modules=[
    #   'django-celery-beat',
    # ],
))
