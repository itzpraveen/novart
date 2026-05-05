from django.db import migrations, models
import django.db.models.deletion


def move_secondary_project_images(apps, schema_editor):
    PublicProjectHighlight = apps.get_model('portal', 'PublicProjectHighlight')
    PublicProjectImage = apps.get_model('portal', 'PublicProjectImage')

    for project in PublicProjectHighlight.objects.all():
        moved = False
        image_pairs = (
            ('image_secondary', 'image_secondary_alt', 1),
            ('image_tertiary', 'image_tertiary_alt', 2),
        )
        for image_field_name, alt_field_name, sort_order in image_pairs:
            image_name = getattr(project, image_field_name)
            if not image_name:
                continue
            PublicProjectImage.objects.create(
                project=project,
                image=image_name,
                alt_text=getattr(project, alt_field_name) or project.title,
                sort_order=sort_order,
            )
            setattr(project, image_field_name, '')
            setattr(project, alt_field_name, '')
            moved = True
        if moved:
            project.save(
                update_fields=[
                    'image_secondary',
                    'image_secondary_alt',
                    'image_tertiary',
                    'image_tertiary_alt',
                ]
            )


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0031_public_work_archive'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicProjectImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('image', models.ImageField(upload_to='public_site/')),
                ('alt_text', models.CharField(blank=True, max_length=255)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gallery_images', to='portal.publicprojecthighlight')),
            ],
            options={
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.RunPython(move_secondary_project_images, migrations.RunPython.noop),
    ]
