from django.db import migrations


def seed_more_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('portal', 'TaskTemplate')
    templates = [
        {
            'title': 'Panchayat/Corporation permit set',
            'description': 'Prepare drawings per KMBR/Kerala Panchayat/Corporation requirements for submission.',
            'status': 'todo',
            'priority': 'high',
            'due_in_days': 10,
        },
        {
            'title': 'Structural coordination',
            'description': 'Send latest arch plans to structural consultant, resolve comments, update drawings.',
            'status': 'in_progress',
            'priority': 'high',
            'due_in_days': 7,
        },
        {
            'title': 'MEP coordination',
            'description': 'Coordinate HVAC/plumbing/electrical with consultants; update reflected ceiling and service plans.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 8,
        },
        {
            'title': 'Material selections',
            'description': 'Shortlist tiles, sanitary, lighting; share options with client for approval.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 5,
        },
        {
            'title': 'Vendor/contractor kick-off',
            'description': 'Kick-off with contractor/vendor; review scope, timelines, and communication cadence.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 3,
        },
        {
            'title': 'Site mobilisation checklist',
            'description': 'Verify site access, storage, power/water, safety signage before execution starts.',
            'status': 'todo',
            'priority': 'high',
            'due_in_days': 2,
        },
        {
            'title': 'Interim payment review',
            'description': 'Review contractor running bill; verify quantities vs progress before payment.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 14,
        },
        {
            'title': 'Snag list & rectification',
            'description': 'Prepare snag list for handover; track closures with photos and dates.',
            'status': 'todo',
            'priority': 'high',
            'due_in_days': 5,
        },
        {
            'title': 'As-built documentation',
            'description': 'Update drawings to as-built; capture changes and final service routes.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 7,
        },
        {
            'title': 'Client handover pack',
            'description': 'Compile warranties, manuals, contacts, and maintenance schedule for client.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 4,
        },
    ]
    for data in templates:
        TaskTemplate.objects.get_or_create(title=data['title'], defaults=data)


def unseed_more_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('portal', 'TaskTemplate')
    titles = [
        'Panchayat/Corporation permit set',
        'Structural coordination',
        'MEP coordination',
        'Material selections',
        'Vendor/contractor kick-off',
        'Site mobilisation checklist',
        'Interim payment review',
        'Snag list & rectification',
        'As-built documentation',
        'Client handover pack',
    ]
    TaskTemplate.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0005_seed_tasktemplates'),
    ]

    operations = [
        migrations.RunPython(seed_more_templates, reverse_code=unseed_more_templates),
    ]
