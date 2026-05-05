from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0030_update_public_phone_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='show_on_homepage',
            field=models.BooleanField(default=True),
        ),
    ]
