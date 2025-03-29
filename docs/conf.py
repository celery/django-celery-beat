import os

from sphinx_celery import conf

globals().update(conf.build_config(
    'django_celery_beat', __file__,
    project='django_celery_beat',
    # version_dev='2.0',
    # version_stable='1.4',
    canonical_url='http://django-celery-beat.readthedocs.io',
    webdomain='',
    github_project='celery/django-celery-beat',
    copyright='2016',
    django_settings='proj.settings',
    include_intersphinx={'python', 'sphinx', 'django', 'celery'},
    path_additions=[os.path.join(os.pardir, 't')],
    html_logo='images/logo.png',
    html_favicon='images/favicon.ico',
    html_prepend_sidebars=[],
    apicheck_ignore_modules=[
        'django_celery_beat.apps',
        r'django_celery_beat.migrations.*',
    ],
    extlinks={
        'github_project': (
            'https://github.com/%s',
            'GitHub project %s',
        ),
        'github_pr': (
            'https://github.com/celery/django-celery-beat/pull/%s',
            'GitHub PR #%s',
        ),
    },
    extra_intersphinx_mapping={
        'django-celery-results': (
            'https://django-celery-results.readthedocs.io/en/latest/',
            None
        ),
    },
    extensions=['sphinxcontrib_django']
))

intersphinx_mapping = globals().get('intersphinx_mapping', {})
intersphinx_mapping['celery'] = (
    'https://celery.readthedocs.io/en/main/', None)
globals().update({'intersphinx_mapping': intersphinx_mapping})
