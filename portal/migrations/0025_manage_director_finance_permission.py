from django.db import migrations


def enable_managing_director_finance(apps, schema_editor):
    role_value = 'managing_director'
    RolePermission = apps.get_model('portal', 'RolePermission')
    existing = RolePermission.objects.filter(role=role_value).first()
    if existing:
        if not existing.finance:
            existing.finance = True
            existing.save(update_fields=['finance'])
        return
    RolePermission.objects.create(
        role=role_value,
        clients=True,
        leads=True,
        projects=True,
        site_visits=True,
        docs=True,
        team=True,
        finance=True,
        invoices=False,
        users=False,
        settings=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0024_firmprofile_invoice_sequence_after'),
    ]

    operations = [
        migrations.RunPython(enable_managing_director_finance, migrations.RunPython.noop),
    ]
