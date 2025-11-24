from django.db import migrations


def seed_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('portal', 'TaskTemplate')
    defaults = [
        {
            'title': 'Site survey',
            'description': 'On-site survey and photos. Capture access constraints and utilities.',
            'status': 'todo',
            'priority': 'high',
            'due_in_days': 3,
        },
        {
            'title': 'Concept package',
            'description': 'Prepare concept layout + mood board for client review.',
            'status': 'in_progress',
            'priority': 'medium',
            'due_in_days': 7,
        },
        {
            'title': 'Authority submission',
            'description': 'Compile drawings, forms, and submit to authority.',
            'status': 'todo',
            'priority': 'high',
            'due_in_days': 14,
        },
        {
            'title': 'Client presentation',
            'description': 'Finalize deck, print boards, schedule with client.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 10,
        },
        {
            'title': 'BOQ and estimate',
            'description': 'Bill of quantities + cost estimate draft.',
            'status': 'todo',
            'priority': 'medium',
            'due_in_days': 12,
        },
    ]
    for data in defaults:
        TaskTemplate.objects.get_or_create(title=data['title'], defaults=data)


def unseed_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('portal', 'TaskTemplate')
    titles = [
        'Site survey',
        'Concept package',
        'Authority submission',
        'Client presentation',
        'BOQ and estimate',
    ]
    TaskTemplate.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0004_tasktemplate'),
    ]

    operations = [
        migrations.RunPython(seed_templates, reverse_code=unseed_templates),
    ]
