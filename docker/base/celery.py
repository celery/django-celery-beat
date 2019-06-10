# Copyright (C) 2019 Sebastian Pipping <sebastian@pipping.org>
# Licensed under the BSD License (3 clause, also known as the new BSD license)

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

app = Celery('mysite')
