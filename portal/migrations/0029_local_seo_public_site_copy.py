from django.db import migrations


COPY_UPDATES = {
    'meta_title': (
        'Novart Architects | Architecture, Interiors, Planning',
        'Novart Architects Edavannapara | Architects in Malappuram, Kerala',
    ),
    'meta_description': (
        'Novart Architects designs residential architecture, interiors, planning, and project delivery for homes and renovations in Kerala.',
        'Novart Architects designs residential architecture, interiors, renovation, planning, and project delivery in Edavannapara, Malappuram, Kondotty, Areekode, Kozhikode, and nearby Kerala towns.',
    ),
}


def improve_local_seo_copy(apps, schema_editor):
    PublicSiteSettings = apps.get_model('portal', 'PublicSiteSettings')
    site = PublicSiteSettings.objects.filter(singleton=True).first()

    if site is None:
        return

    changed_fields = []
    for field_name, (old_value, new_value) in COPY_UPDATES.items():
        if getattr(site, field_name) == old_value:
            setattr(site, field_name, new_value)
            changed_fields.append(field_name)

    if changed_fields:
        site.save(update_fields=changed_fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0028_public_project_gallery_and_copy'),
    ]

    operations = [
        migrations.RunPython(improve_local_seo_copy, noop),
    ]
