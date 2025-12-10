from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    """
    Alter Receipt model:
    - Make payment required (receipt is generated FROM a payment)
    - Remove amount, method, reference, attachment fields (come from payment now)
    - Remove lead field
    - Rename received_by to generated_by
    """

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0012_receipt'),
    ]

    operations = [
        # First, delete any receipts without payments (shouldn't exist, but safety)
        migrations.RunSQL(
            "DELETE FROM portal_receipt WHERE payment_id IS NULL;",
            migrations.RunSQL.noop,
        ),
        # Remove fields that are now derived from payment
        migrations.RemoveField(
            model_name='receipt',
            name='amount',
        ),
        migrations.RemoveField(
            model_name='receipt',
            name='method',
        ),
        migrations.RemoveField(
            model_name='receipt',
            name='reference',
        ),
        migrations.RemoveField(
            model_name='receipt',
            name='attachment',
        ),
        migrations.RemoveField(
            model_name='receipt',
            name='lead',
        ),
        # Rename received_by to generated_by
        migrations.RenameField(
            model_name='receipt',
            old_name='received_by',
            new_name='generated_by',
        ),
        # Update notes field help text
        migrations.AlterField(
            model_name='receipt',
            name='notes',
            field=models.TextField(blank=True, help_text='Additional notes to print on receipt'),
        ),
        # Make payment required (non-nullable)
        migrations.AlterField(
            model_name='receipt',
            name='payment',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='receipt',
                to='portal.payment'
            ),
        ),
    ]
