from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0015_finance_audit_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='objective',
            field=models.TextField(blank=True, default='', help_text='What is the goal of this task?'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='expected_output',
            field=models.TextField(default='', help_text='What should be delivered/decided?'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='deliverables',
            field=models.TextField(blank=True, default='', help_text='Checklist or bullet deliverables (one per line).'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='references',
            field=models.TextField(blank=True, default='', help_text='Links or references (one per line).'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='constraints',
            field=models.TextField(blank=True, default='', help_text='Any constraints, budgets, or rules to follow.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='watchers',
            field=models.ManyToManyField(
                blank=True,
                help_text='Users watching this task.',
                related_name='watched_tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='TaskComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('body', models.TextField()),
                ('is_system', models.BooleanField(default=False)),
                (
                    'author',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='task_comments',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='comments',
                        to='portal.task',
                    ),
                ),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='TaskCommentAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='task_comments/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                (
                    'comment',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='attachments',
                        to='portal.taskcomment',
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

