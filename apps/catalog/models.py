from django.db import models


class Treatment(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    meta = models.JSONField(default=dict, blank=True)  # JSONB en Postgres
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
