"""Model querysets."""
from django.db import models


class PeriodicTaskQuerySet(models.QuerySet):
    """QuerySet for the PeriodicTask model that will be used as it's default manager."""

    def enabled(self):
        return self.filter(enabled=True)
