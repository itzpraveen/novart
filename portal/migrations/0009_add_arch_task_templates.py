from django.db import migrations


def add_arch_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('portal', 'TaskTemplate')
    titles = [
        "Plan Designing",
        "Exterior 3D",
        "Floor Plan Setting",
        "Walk Through",
        "Interior 3D",
        "Working Drawing",
        "Structural Drawing",
        "Electrical Drawing",
        "Plumbing Drawing",
        "Interior 2D Detailed Drawing",
        "Interior 2D Ceiling Drawing",
        "Estimation",
        "Occupancy Application",
        "Permit Application",
        "Land Cutting Application",
        "Regularisation Permit Application",
        "Regularisation Completion Application",
        "Numbering Application",
        "Valuation",
        "Stage Certificate",
    ]
    existing = set(TaskTemplate.objects.values_list('title', flat=True))
    for title in titles:
        if title in existing:
            continue
        TaskTemplate.objects.create(title=title, description="", status="todo", priority="medium", due_in_days=None)


def remove_arch_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('portal', 'TaskTemplate')
    titles = [
        "Plan Designing",
        "Exterior 3D",
        "Floor Plan Setting",
        "Walk Through",
        "Interior 3D",
        "Working Drawing",
        "Structural Drawing",
        "Electrical Drawing",
        "Plumbing Drawing",
        "Interior 2D Detailed Drawing",
        "Interior 2D Ceiling Drawing",
        "Estimation",
        "Occupancy Application",
        "Permit Application",
        "Land Cutting Application",
        "Regularisation Permit Application",
        "Regularisation Completion Application",
        "Numbering Application",
        "Valuation",
        "Stage Certificate",
    ]
    TaskTemplate.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0008_lead_planning_and_invoice_lead'),
    ]

    operations = [
        migrations.RunPython(add_arch_templates, remove_arch_templates),
    ]
