from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0032_publicprojectimage'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='instagram_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='youtube_url',
            field=models.URLField(blank=True),
        ),
    ]
