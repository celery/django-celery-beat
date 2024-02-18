#!/usr/bin/env python3

import codecs
import os
import re
import sys

import setuptools
import setuptools.command.test

try:
    import platform
    _pyimp = platform.python_implementation
except (AttributeError, ImportError):
    def _pyimp():
        return 'Python'

NAME = 'django-celery-beat'
PACKAGE = 'django_celery_beat'

E_UNSUPPORTED_PYTHON = f'{NAME} 1.0 requires %s %s or later!'

PYIMP = _pyimp()
PY38_OR_LESS = sys.version_info < (3, 8)
PYPY_VERSION = getattr(sys, 'pypy_version_info', None)
PYPY24_ATLEAST = PYPY_VERSION and PYPY_VERSION >= (2, 4)

if PY38_OR_LESS and not PYPY24_ATLEAST:
    raise Exception(E_UNSUPPORTED_PYTHON % (PYIMP, '3.8'))

# -*- Classifiers -*-

classes = """
    Development Status :: 5 - Production/Stable
    License :: OSI Approved :: BSD License
    Programming Language :: Python
    Programming Language :: Python :: 3
    Programming Language :: Python :: 3.8
    Programming Language :: Python :: 3.9
    Programming Language :: Python :: 3.10
    Programming Language :: Python :: 3.11
    Programming Language :: Python :: 3.12
    Programming Language :: Python :: Implementation :: CPython
    Programming Language :: Python :: Implementation :: PyPy
    Framework :: Django
    Framework :: Django :: 3.2
    Framework :: Django :: 4.1
    Framework :: Django :: 4.2
    Framework :: Django :: 5.0
    Operating System :: OS Independent
    Topic :: Communications
    Topic :: System :: Distributed Computing
    Topic :: Software Development :: Libraries :: Python Modules
"""
classifiers = [s.strip() for s in classes.split('\n') if s]

# -*- Distribution Meta -*-

re_meta = re.compile(r'__(\w+?)__\s*=\s*(.*)')
re_doc = re.compile(r'^"""(.+?)"""')


def add_default(m):
    attr_name, attr_value = m.groups()
    return ((attr_name, attr_value.strip("\"'")),)


def add_doc(m):
    return (('doc', m.groups()[0]),)


pats = {re_meta: add_default,
        re_doc: add_doc}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, PACKAGE, '__init__.py')) as meta_fh:
    meta = {}
    for line in meta_fh:
        if line.strip() == '# -eof meta-':
            break
        for pattern, handler in pats.items():
            m = pattern.match(line.strip())
            if m:
                meta.update(handler(m))

# -*- Installation Requires -*-


def strip_comments(line):
    return line.split('#', 1)[0].strip()


def _pip_requirement(req):
    if req.startswith('-r '):
        _, path = req.split()
        return reqs(*path.split('/'))
    return [req]


def _reqs(*f):
    return [
        _pip_requirement(r) for r in (
            strip_comments(line) for line in open(
                os.path.join(os.getcwd(), 'requirements', *f)).readlines()
        ) if r]


def reqs(*f):
    return [req for subreq in _reqs(*f) for req in subreq]

# -*- Long Description -*-


if os.path.exists('README.rst'):
    long_description = codecs.open('README.rst', 'r', 'utf-8').read()
    long_description_content_type = 'text/x-rst'
else:
    long_description = f'See http://pypi.python.org/pypi/{NAME}'
    long_description_content_type = 'text/markdown'

# -*- %%% -*-


class pytest(setuptools.command.test.test):
    user_options = [('pytest-args=', 'a', 'Arguments to pass to pytest')]

    def initialize_options(self):
        setuptools.command.test.test.initialize_options(self)
        self.pytest_args = []

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(self.pytest_args))


setuptools.setup(
    name=NAME,
    packages=setuptools.find_packages(exclude=[
        'ez_setup', 't', 't.*',
    ]),
    version=meta['version'],
    description=meta['doc'],
    long_description=long_description,
    long_description_content_type=long_description_content_type,
    keywords='django celery beat periodic task database',
    author=meta['author'],
    author_email=meta['contact'],
    url=meta['homepage'],
    platforms=['any'],
    license='BSD',
    install_requires=reqs('default.txt') + reqs('runtime.txt'),
    tests_require=reqs('test.txt') + reqs('test-django.txt'),
    cmdclass={'test': pytest},
    classifiers=classifiers,
    entry_points={
        'celery.beat_schedulers': [
            'django = django_celery_beat.schedulers:DatabaseScheduler',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
