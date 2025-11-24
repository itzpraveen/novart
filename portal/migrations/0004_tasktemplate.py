from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0003_invoice_line_and_firm_profile'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                (
                    'status',
                    models.CharField(
                        choices=[('todo', 'To Do'), ('in_progress', 'In Progress'), ('done', 'Done')],
                        default='todo',
                        max_length=32,
                    ),
                ),
                (
                    'priority',
                    models.CharField(
                        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
                        default='medium',
                        max_length=32,
                    ),
                ),
                (
                    'due_in_days',
                    models.PositiveIntegerField(
                        blank=True, help_text='If set, due date will default to today + this many days.', null=True
                    ),
                ),
            ],
            options={
                'ordering': ['title'],
            },
        ),
    ]
