# To release a new version to the Python Packaging Index (PyPI)
Review the `publish-to-pypi` job in `.github/workflows/build.yml`.
* [ ] Type `pre-commit.ci run` in an open or closed pull request that was created by @pre-commit.ci to ensure pre-commit is up to date and all tests pass.
* [ ] Go to https://github.com/celery/django-celery-beat/releases and click the `Draft a new release` button.
* [ ] Use that text or something similar to update `Changelog` and ensure releaser information and release date are correct.
* [ ] Run `bump2version` as discussed in #790 and ensure the four files have the new version.
* [ ] Merge all `pre-commit`, `Changelog`, and `bump2version` changes.
* [ ] Return to https://github.com/celery/django-celery-beat/releases and convert the Draft to a Release.
* [ ] Go to https://github.com/celery/django-celery-beat/actions to ensure all tests and publish to PyPI are green.
* [ ] Go to https://pypi.org/project/django-celery-beat and ensure the new version is present.
