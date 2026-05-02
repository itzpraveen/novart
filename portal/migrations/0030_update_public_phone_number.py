from django.db import migrations


NEW_PHONE_DISPLAY = '+91 88913 23362'
NEW_WHATSAPP_NUMBER = '918891323362'


def update_public_phone_number(apps, schema_editor):
    PublicSiteSettings = apps.get_model('portal', 'PublicSiteSettings')
    FirmProfile = apps.get_model('portal', 'FirmProfile')

    site = PublicSiteSettings.objects.filter(singleton=True).first()
    if site is not None:
        changed_fields = []
        if site.phone_display != NEW_PHONE_DISPLAY:
            site.phone_display = NEW_PHONE_DISPLAY
            changed_fields.append('phone_display')
        if site.whatsapp_number != NEW_WHATSAPP_NUMBER:
            site.whatsapp_number = NEW_WHATSAPP_NUMBER
            changed_fields.append('whatsapp_number')
        if changed_fields:
            site.save(update_fields=changed_fields)

    firm = FirmProfile.objects.filter(singleton=True).first()
    if firm is not None and firm.phone != NEW_PHONE_DISPLAY:
        firm.phone = NEW_PHONE_DISPLAY
        firm.save(update_fields=['phone'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0029_local_seo_public_site_copy'),
    ]

    operations = [
        migrations.RunPython(update_public_phone_number, noop),
    ]
