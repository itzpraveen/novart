from django.db import migrations


def seed_public_site_content(apps, schema_editor):
    FirmProfile = apps.get_model('portal', 'FirmProfile')
    PublicProcessStep = apps.get_model('portal', 'PublicProcessStep')
    PublicProjectHighlight = apps.get_model('portal', 'PublicProjectHighlight')
    PublicService = apps.get_model('portal', 'PublicService')
    PublicSiteSettings = apps.get_model('portal', 'PublicSiteSettings')

    firm_profile = FirmProfile.objects.filter(singleton=True).first()
    phone_display = (firm_profile.phone if firm_profile and firm_profile.phone else '+91 00000 00000').strip()
    whatsapp_number = ''.join(ch for ch in phone_display if ch.isdigit()) or '910000000000'

    site, _ = PublicSiteSettings.objects.get_or_create(
        singleton=True,
        defaults={
            'brand_name': 'Novart',
            'brand_suffix': 'Architects',
            'hero_heading': 'Architecture, interiors, planning, and project management.',
            'hero_supporting_text': 'We design spaces that inspire and enhance lives with tailored solutions grounded in innovation, creativity, and sustainability.',
            'hero_cta_phone_label': 'Call Us',
            'hero_cta_whatsapp_label': 'WhatsApp Us',
            'phone_display': phone_display,
            'whatsapp_number': whatsapp_number,
            'email': firm_profile.email if firm_profile and firm_profile.email else 'hello@novartarchitects.com',
            'address': firm_profile.address if firm_profile and firm_profile.address else 'Kerala, India',
            'services_heading': 'Services',
            'services_intro': 'A multidisciplinary practice delivering architecture, interiors, planning, and project management in one coherent design process.',
            'process_heading': 'Process',
            'process_intro': 'From first brief to final handover, each phase is shaped to keep design intent, clarity, and execution aligned.',
            'work_heading': 'Selected Work',
            'work_intro': 'Launch visuals are atmospheric stand-ins for the kinds of places Novart shapes across architecture and interiors.',
            'studio_heading': 'Studio',
            'studio_body': 'Sustainability is a working principle, not a slogan. Novart balances atmosphere, functionality, and responsible material thinking to create spaces that feel generous over time.',
            'contact_heading': 'Contact',
            'contact_intro': 'Speak with Novart directly to discuss your site, brief, renovation, or new build.',
            'hero_art_key': 'courtyard-house',
            'studio_art_key': 'atelier-interior',
            'meta_title': 'Novart Architects | Architecture, Interiors, Planning, Project Management',
            'meta_description': 'Novart Architects designs architecture, interiors, planning, and project management services for spaces that inspire and enhance everyday life.',
        },
    )

    services = [
        ('Architectural Design', 'Homes, workspaces, and built environments shaped around light, movement, and long-term use.'),
        ('Interior Design', 'Spatial detailing, materials, and atmosphere developed as part of the architecture rather than after it.'),
        ('Planning', 'Site-responsive planning that balances approvals, feasibility, and the way a place should actually feel.'),
        ('Project Management', 'End-to-end coordination that keeps decisions, timelines, and execution tied to the design vision.'),
    ]
    for index, (title, description) in enumerate(services, start=1):
        PublicService.objects.get_or_create(
            site=site,
            title=title,
            defaults={'description': description, 'sort_order': index},
        )

    process_steps = [
        ('01', 'Brief', 'We start with the site, your goals, and the daily life or work patterns the space needs to support.'),
        ('02', 'Shape', 'Concepts are translated into planning, form, material direction, and interior atmosphere.'),
        ('03', 'Develop', 'Drawings, details, coordination, and approvals are refined into a buildable system.'),
        ('04', 'Deliver', 'Execution is monitored closely so the finished space retains its intended clarity and character.'),
    ]
    for index, (step_label, title, description) in enumerate(process_steps, start=1):
        PublicProcessStep.objects.get_or_create(
            site=site,
            step_label=step_label,
            title=title,
            defaults={'description': description, 'sort_order': index},
        )

    project_highlights = [
        ('Courtyard Residence', 'Architecture', 'Private Home', 'A quiet residential concept arranged around shade, breezeways, and a central planted court.', 'courtyard-house'),
        ('Atelier Living', 'Interiors', 'Urban Apartment', 'An interior study in timber, stone, and calm daylight for a more tactile daily routine.', 'atelier-interior'),
        ('Horizon Campus', 'Planning', 'Mixed-Use Site', 'A master planning concept aligning circulation, build phases, and long-term site potential.', 'horizon-masterplan'),
    ]
    for index, (title, project_type, location, description, art_key) in enumerate(project_highlights, start=1):
        PublicProjectHighlight.objects.get_or_create(
            site=site,
            title=title,
            defaults={
                'project_type': project_type,
                'location': location,
                'description': description,
                'art_key': art_key,
                'sort_order': index,
            },
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0026_publicsitesettings_publicservice_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_public_site_content, noop),
    ]
