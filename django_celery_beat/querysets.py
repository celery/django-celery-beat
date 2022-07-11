"""Model querysets."""
from django.db import models


class PeriodicTaskQuerySet(models.QuerySet):
    """QuerySet for PeriodicTask."""

    def enabled(self):
        return self.filter(enabled=True)
