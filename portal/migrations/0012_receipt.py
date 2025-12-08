from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0011_rolepermission'),
    ]

    operations = [
        migrations.CreateModel(
            name='Receipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('receipt_number', models.CharField(max_length=64, unique=True)),
                ('receipt_date', models.DateField(default=django.utils.timezone.now)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('method', models.CharField(blank=True, max_length=50)),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='receipts/')),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts', to='portal.client')),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='portal.invoice')),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts', to='portal.lead')),
                ('payment', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipt', to='portal.payment')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts', to='portal.project')),
                ('received_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-receipt_date', '-created_at'],
            },
        ),
    ]
