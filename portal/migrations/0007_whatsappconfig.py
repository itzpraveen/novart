from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0006_more_tasktemplates'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('enabled', models.BooleanField(default=False)),
                ('phone_number_id', models.CharField(blank=True, max_length=64)),
                ('from_number', models.CharField(blank=True, max_length=32)),
                ('api_token', models.TextField(blank=True)),
                ('default_language', models.CharField(blank=True, default='en', max_length=10)),
            ],
            options={
                'verbose_name': 'WhatsApp Configuration',
            },
        ),
    ]
