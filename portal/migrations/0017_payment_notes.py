from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0016_task_rich_fields_and_comments'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='notes',
            field=models.TextField(blank=True, default='', help_text='Internal notes about this payment.'),
            preserve_default=False,
        ),
    ]

