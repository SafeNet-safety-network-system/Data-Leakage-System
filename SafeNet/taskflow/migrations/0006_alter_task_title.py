# Generated by Django 5.0 on 2024-09-21 06:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taskflow', '0005_task_start_date_alter_project_end_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='title',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
