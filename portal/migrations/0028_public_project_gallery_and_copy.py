from django.db import migrations, models


DEFAULT_COPY_UPDATES = {
    'hero_heading': (
        'Architecture, interiors, planning, and project management.',
        'Homes and interiors shaped around light, climate, and craft.',
    ),
    'hero_supporting_text': (
        'We design spaces that inspire and enhance lives with tailored solutions grounded in innovation, creativity, and sustainability.',
        'Architecture, interiors, planning, and project delivery kept under one clear studio process.',
    ),
    'services_heading': ('Services', 'Practice'),
    'services_intro': (
        'A multidisciplinary practice delivering architecture, interiors, planning, and project management in one coherent design process.',
        'Architecture, interiors, planning, and project management handled as one accountable design process.',
    ),
    'process_heading': ('Process', 'From site to handover'),
    'process_intro': (
        'From first brief to final handover, each phase is shaped to keep design intent, clarity, and execution aligned.',
        'A clear sequence keeps the brief, drawings, approvals, materials, and site execution moving together.',
    ),
    'work_heading': ('Selected Work', 'Selected Homes'),
    'work_intro': (
        'Launch visuals are atmospheric stand-ins for the kinds of places Novart shapes across architecture and interiors.',
        'Recent residences and renovations can be shown through facade, interior, and site moments from the same project.',
    ),
    'studio_heading': ('Studio', 'Measured by how the space lives'),
    'studio_body': (
        'Sustainability is a working principle, not a slogan. Novart balances atmosphere, functionality, and responsible material thinking to create spaces that feel generous over time.',
        'Novart designs around climate, proportion, material durability, and the everyday routines that make a building feel settled over time.',
    ),
    'contact_heading': ('Contact', 'Start with your site'),
    'contact_intro': (
        'Speak with Novart directly to discuss your site, brief, renovation, or new build.',
        'Share the plot, renovation, or interior brief and speak directly with the studio.',
    ),
    'meta_title': (
        'Novart Architects | Architecture, Interiors, Planning, Project Management',
        'Novart Architects | Architecture, Interiors, Planning',
    ),
    'meta_description': (
        'Novart Architects designs architecture, interiors, planning, and project management services for spaces that inspire and enhance everyday life.',
        'Novart Architects designs residential architecture, interiors, planning, and project delivery for homes and renovations in Kerala.',
    ),
}


def improve_default_public_site_copy(apps, schema_editor):
    PublicSiteSettings = apps.get_model('portal', 'PublicSiteSettings')
    site = PublicSiteSettings.objects.filter(singleton=True).first()

    if site is None:
        return

    changed_fields = []
    for field_name, (old_value, new_value) in DEFAULT_COPY_UPDATES.items():
        if getattr(site, field_name) == old_value:
            setattr(site, field_name, new_value)
            changed_fields.append(field_name)

    if changed_fields:
        site.save(update_fields=changed_fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0027_seed_public_site_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='image_secondary',
            field=models.ImageField(blank=True, null=True, upload_to='public_site/'),
        ),
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='image_secondary_alt',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='image_tertiary',
            field=models.ImageField(blank=True, null=True, upload_to='public_site/'),
        ),
        migrations.AddField(
            model_name='publicprojecthighlight',
            name='image_tertiary_alt',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(improve_default_public_site_copy, noop),
    ]
