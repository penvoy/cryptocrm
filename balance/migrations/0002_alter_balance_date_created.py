# Generated by Django 4.2.13 on 2024-06-25 13:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('balance', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='balance',
            name='date_created',
            field=models.FloatField(),
        ),
    ]