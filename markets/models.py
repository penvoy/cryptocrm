from django.db import models

# Create your models here.
class Markets(models.Model):
    """
    Таблица: Биржи

    :param
        name - наименование,
        uid - уникальный идентификатор
        private_key - приватный ключ
        public_key - публичный ключ
        account - аккаунт биржи
    
    """

    name = models.TextField(blank=True)
    uid = models.TextField(blank=True, null=True)
    private_key = models.TextField(blank=True)
    public_key = models.TextField(blank=True, null=True)
    account = models.TextField(blank=True)

    