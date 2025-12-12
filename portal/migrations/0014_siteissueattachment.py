from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0013_alter_receipt_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteIssueAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='site_issues/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('issue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='portal.siteissue')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

