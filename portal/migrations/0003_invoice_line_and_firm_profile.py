from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0002_project_site_engineer'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='discount_percent',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.CreateModel(
            name='FirmProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(blank=True, max_length=255)),
                ('address', models.TextField(blank=True)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('tax_id', models.CharField(blank=True, max_length=100)),
                ('bank_name', models.CharField(blank=True, max_length=255)),
                ('bank_account_name', models.CharField(blank=True, max_length=255)),
                ('bank_account_number', models.CharField(blank=True, max_length=100)),
                ('bank_ifsc', models.CharField(blank=True, max_length=50)),
                ('upi_id', models.CharField(blank=True, max_length=100)),
                ('terms', models.TextField(blank=True)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='firm/')),
                ('singleton', models.BooleanField(default=True, unique=True)),
            ],
            options={
                'verbose_name': 'Firm Profile',
            },
        ),
        migrations.CreateModel(
            name='InvoiceLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='portal.invoice')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
