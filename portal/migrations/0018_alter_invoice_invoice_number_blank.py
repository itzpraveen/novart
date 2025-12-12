from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0017_payment_notes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='invoice_number',
            field=models.CharField(blank=True, max_length=50, unique=True),
        ),
    ]

