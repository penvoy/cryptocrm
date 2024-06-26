from django.db import models

class Balance(models.Model):
    """
    Таблица: Баланс
    """
    date_created = models.TextField(null=False)
    data = models.JSONField(blank=True)
    result = models.FloatField(blank=True)
    locked = models.FloatField(blank=True)