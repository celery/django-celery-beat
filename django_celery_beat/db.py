from __future__ import absolute_import

from contextlib import contextmanager
from django.db import transaction

try:
    from django.db.transaction import atomic  # noqa
except ImportError:  # pragma: no cover

    try:
        from django.db.transaction import Transaction  # noqa
    except ImportError:
        @contextmanager
        def commit_on_success(*args, **kwargs):
            try:
                transaction.enter_transaction_management(*args, **kwargs)
                transaction.managed(True, *args, **kwargs)
                try:
                    yield
                except:
                    if transaction.is_dirty(*args, **kwargs):
                        transaction.rollback(*args, **kwargs)
                    raise
                else:
                    if transaction.is_dirty(*args, **kwargs):
                        try:
                            transaction.commit(*args, **kwargs)
                        except:
                            transaction.rollback(*args, **kwargs)
                            raise
            finally:
                transaction.leave_transaction_management(*args, **kwargs)
    else:  # pragma: no cover
        from django.db.transaction import commit_on_success  # noqa

    commit_unless_managed = transaction.commit_unless_managed
    rollback_unless_managed = transaction.rollback_unless_managed
else:
    @contextmanager
    def commit_on_success(using=None):  # noqa
        connection = transaction.get_connection(using)
        if connection.features.autocommits_when_autocommit_is_off:
            # ignore stupid warnings and errors
            yield
        else:
            with transaction.atomic(using):
                yield

    def commit_unless_managed(*args, **kwargs):  # noqa
        pass

    def rollback_unless_managed(*args, **kwargs):  # noqa
        pass
