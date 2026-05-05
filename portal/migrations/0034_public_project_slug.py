from django.db import migrations, models
from django.utils.text import slugify


def populate_project_slugs(apps, schema_editor):
    PublicProjectHighlight = apps.get_model('portal', 'PublicProjectHighlight')
    used_slugs = set()

    for project in PublicProjectHighlight.objects.order_by('sort_order', 'id'):
        base_slug = slugify(project.title) or 'work'
        base_slug = base_slug[:170].strip('-') or 'work'
        candidate = base_slug
        counter = 2
        while candidate in used_slugs or PublicProjectHighlight.objects.exclude(pk=project.pk).filter(slug=candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base_slug[:180 - len(suffix)].strip('-')}{suffix}"
            counter += 1
        project.slug = candidate
        project.save(update_fields=['slug'])
        used_slugs.add(candidate)


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0033_public_project_social_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='slug',
            field=models.SlugField(blank=True, db_index=False, max_length=180),
        ),
        migrations.RunPython(populate_project_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='publicprojecthighlight',
            name='slug',
            field=models.SlugField(blank=True, max_length=180, unique=True),
        ),
    ]
