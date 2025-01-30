# Generated by Django 5.1.5 on 2025-01-28 10:59

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_comment_alter_ticket_comments_decision_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticket',
            name='comments',
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='decision',
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='description',
        ),
        migrations.AddField(
            model_name='comment',
            name='ticket',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='core.ticket'),
        ),
        migrations.AddField(
            model_name='decision',
            name='ticket',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='decisions', to='core.ticket'),
        ),
        migrations.AddField(
            model_name='description',
            name='ticket',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='description', to='core.ticket'),
        ),
    ]
