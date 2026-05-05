import json
import re

from django.conf import settings
from django.shortcuts import redirect, render
from django.templatetags.static import static

from .models import FirmProfile, PublicSiteSettings


ARTWORK_ASSET_PATHS = {
    'courtyard-house': 'img/public/courtyard-house.svg',
    'atelier-interior': 'img/public/atelier-interior.svg',
    'horizon-masterplan': 'img/public/horizon-masterplan.svg',
}

PUBLIC_EXACT_PATHS = {
    '/',
    '/favicon.ico',
    '/manifest.json',
    '/robots.txt',
    '/service-worker.js',
    '/sitemap.xml',
    '/work',
    '/work/',
}

LOCAL_SERVICE_AREAS = [
    'Edavannapara',
    'Malappuram',
    'Kondotty',
    'Areekode',
    'Kozhikode',
    'Kerala',
]

LOCAL_SEO_HEADING = 'Architects near Edavannapara and Malappuram'
LOCAL_SEO_BODY = (
    'Novart Architects works with homeowners and site owners across Edavannapara, Malappuram, '
    'Kondotty, Areekode, Kozhikode, and nearby Kerala towns for architecture, interiors, '
    'renovation, planning, and project management.'
)


def _normalized_host(raw_host: str) -> str:
    return (raw_host or '').split(':', 1)[0].lower()


def is_erp_host(request) -> bool:
    erp_hosts = {_normalized_host(host) for host in getattr(settings, 'ERP_HOSTS', []) if host}
    return _normalized_host(request.get_host()) in erp_hosts


def is_public_host(request) -> bool:
    public_hosts = {_normalized_host(host) for host in getattr(settings, 'PUBLIC_SITE_HOSTS', []) if host}
    host = _normalized_host(request.get_host())
    if public_hosts:
        return host in public_hosts
    return not is_erp_host(request)


def is_public_path(path: str) -> bool:
    static_url = getattr(settings, 'STATIC_URL', '/static/')
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    return path in PUBLIC_EXACT_PATHS or path.startswith(static_url) or path.startswith(media_url)


def erp_redirect_url(request) -> str | None:
    base_url = getattr(settings, 'ERP_BASE_URL', '').rstrip('/')
    if not base_url:
        return None
    return f"{base_url}{request.get_full_path()}"


def _safe_image_url(image_field) -> str:
    if not image_field:
        return ''
    try:
        if not image_field.name or not image_field.storage.exists(image_field.name):
            return ''
        return image_field.url
    except (AttributeError, OSError, ValueError):
        return ''


def _artwork_url(image_field, art_key: str) -> str:
    image_url = _safe_image_url(image_field)
    if image_url:
        return image_url
    return static(ARTWORK_ASSET_PATHS.get(art_key, ARTWORK_ASSET_PATHS['courtyard-house']))


def _phone_href(phone_display: str) -> str:
    normalized = re.sub(r'[^\d+]', '', phone_display or '')
    return f"tel:{normalized}" if normalized else ''


def _whatsapp_href(phone_number: str) -> str:
    digits = re.sub(r'\D', '', phone_number or '')
    return f"https://wa.me/{digits}" if digits else ''


def _canonical_public_url(path: str = '/') -> str:
    configured = getattr(settings, 'PUBLIC_SITE_CANONICAL_URL', '').rstrip('/')
    if configured:
        return f"{configured}{path}"
    public_hosts = [host for host in getattr(settings, 'PUBLIC_SITE_HOSTS', []) if host]
    host = public_hosts[0] if public_hosts else 'novartarchitects.com'
    return f"https://{_normalized_host(host)}{path}"


def _absolute_public_url(url: str) -> str:
    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    if not url.startswith('/'):
        url = f"/{url}"
    return _canonical_public_url(url)


def _local_business_schema(site, logo_url: str, hero_image_url: str, project_cards: list[dict]) -> str:
    phone = getattr(site, 'phone_display', '') or getattr(site, 'whatsapp_number', '')
    address = getattr(site, 'address', '') or 'Edavannapara, Malappuram, Kerala'
    images = [hero_image_url, *[project['image_url'] for project in project_cards[:3]]]
    schema = {
        '@context': 'https://schema.org',
        '@type': ['LocalBusiness', 'ArchitecturalService'],
        '@id': f"{_canonical_public_url()}#localbusiness",
        'name': f"{site.brand_name} {site.brand_suffix}".strip(),
        'url': _canonical_public_url(),
        'logo': _absolute_public_url(logo_url),
        'image': [_absolute_public_url(image) for image in images if image],
        'description': getattr(site, 'meta_description', '') or getattr(site, 'hero_supporting_text', ''),
        'telephone': phone,
        'email': getattr(site, 'email', ''),
        'priceRange': 'Contact for quote',
        'address': {
            '@type': 'PostalAddress',
            'streetAddress': address,
            'addressLocality': 'Edavannapara',
            'addressRegion': 'Kerala',
            'postalCode': '673645',
            'addressCountry': 'IN',
        },
        'areaServed': [{'@type': 'Place', 'name': area} for area in LOCAL_SERVICE_AREAS],
        'knowsAbout': [
            'Architectural design',
            'Interior design',
            'Residential architecture',
            'Home renovation',
            'Planning',
            'Project management',
        ],
        'sameAs': [_canonical_public_url()],
    }
    return json.dumps(schema, ensure_ascii=False, separators=(',', ':'))


def _public_site_defaults() -> dict:
    return {
        'brand_name': 'Novart',
        'brand_suffix': 'Architects',
        'hero_heading': 'Homes and interiors shaped around light, climate, and craft.',
        'hero_supporting_text': 'Architecture, interiors, planning, and project delivery kept under one clear studio process.',
        'hero_cta_phone_label': 'Call Us',
        'hero_cta_whatsapp_label': 'WhatsApp Us',
        'phone_display': '+91 00000 00000',
        'whatsapp_number': '910000000000',
        'email': 'hello@novartarchitects.com',
        'address': 'Kerala, India',
        'services_heading': 'Practice',
        'services_intro': 'Architecture, interiors, planning, and project management handled as one accountable design process.',
        'process_heading': 'From site to handover',
        'process_intro': 'A clear sequence keeps the brief, drawings, approvals, materials, and site execution moving together.',
        'work_heading': 'Selected Homes',
        'work_intro': 'Recent residences and renovations can be shown through facade, interior, and site moments from the same project.',
        'studio_heading': 'Measured by how the space lives',
        'studio_body': 'Novart designs around climate, proportion, material durability, and the everyday routines that make a building feel settled over time.',
        'contact_heading': 'Start with your site',
        'contact_intro': 'Share the plot, renovation, or interior brief and speak directly with the studio.',
        'hero_art_key': 'courtyard-house',
        'studio_art_key': 'atelier-interior',
        'meta_title': 'Novart Architects Edavannapara | Architects in Malappuram, Kerala',
        'meta_description': 'Novart Architects designs residential architecture, interiors, renovation, planning, and project delivery in Edavannapara, Malappuram, Kondotty, Areekode, Kozhikode, and nearby Kerala towns.',
    }


def _default_services():
    return [
        {'title': 'Architectural Design', 'description': 'Homes, workspaces, and built environments shaped around light, movement, and long-term use.'},
        {'title': 'Interior Design', 'description': 'Spatial detailing, materials, and atmosphere developed as part of the architecture rather than after it.'},
        {'title': 'Planning', 'description': 'Site-responsive planning that balances approvals, feasibility, and the way a place should actually feel.'},
        {'title': 'Project Management', 'description': 'End-to-end coordination that keeps decisions, timelines, and execution tied to the design vision.'},
    ]


def _default_process_steps():
    return [
        {'step_label': '01', 'title': 'Brief', 'description': 'We start with the site, your goals, and the daily life or work patterns the space needs to support.'},
        {'step_label': '02', 'title': 'Shape', 'description': 'Concepts are translated into planning, form, material direction, and interior atmosphere.'},
        {'step_label': '03', 'title': 'Develop', 'description': 'Drawings, details, coordination, and approvals are refined into a buildable system.'},
        {'step_label': '04', 'title': 'Deliver', 'description': 'Execution is monitored closely so the finished space retains its intended clarity and character.'},
    ]


def _default_projects():
    return [
        {
            'title': 'Courtyard Residence',
            'project_type': 'Architecture',
            'location': 'Private Home',
            'description': 'A quiet residential concept arranged around shade, breezeways, and a central planted court.',
            'art_key': 'courtyard-house',
        },
        {
            'title': 'Atelier Living',
            'project_type': 'Interiors',
            'location': 'Urban Apartment',
            'description': 'An interior study in timber, stone, and calm daylight for a more tactile daily routine.',
            'art_key': 'atelier-interior',
        },
        {
            'title': 'Horizon Campus',
            'project_type': 'Planning',
            'location': 'Mixed-Use Site',
            'description': 'A master planning concept aligning circulation, build phases, and long-term site potential.',
            'art_key': 'horizon-masterplan',
        },
    ]


def _project_image_items(project) -> list[dict]:
    images = [
        {
            'url': _artwork_url(project.image, project.art_key),
            'alt': project.image_alt or project.title,
        }
    ]
    extra_image_fields = (
        ('image_secondary', 'image_secondary_alt'),
        ('image_tertiary', 'image_tertiary_alt'),
    )
    for image_field_name, alt_field_name in extra_image_fields:
        image_url = _safe_image_url(getattr(project, image_field_name, None))
        if image_url:
            images.append(
                {
                    'url': image_url,
                    'alt': getattr(project, alt_field_name, '') or project.title,
                }
            )
    for gallery_image in project.gallery_images.all():
        image_url = _safe_image_url(gallery_image.image)
        if image_url:
            images.append(
                {
                    'url': image_url,
                    'alt': gallery_image.alt_text or project.title,
                }
            )
    return images


def _project_card_from_model(project) -> dict:
    images = _project_image_items(project)
    visible_images = images[:3]
    return {
        'title': project.title,
        'project_type': project.project_type,
        'location': project.location,
        'description': project.description,
        'show_on_homepage': project.show_on_homepage,
        'images': images,
        'visible_images': visible_images,
        'hidden_images': images[3:],
        'hidden_image_count': max(len(images) - len(visible_images), 0),
        'image_url': images[0]['url'],
        'image_alt': images[0]['alt'],
    }


def _project_card_from_defaults(project: dict) -> dict:
    image = {
        'url': static(ARTWORK_ASSET_PATHS[project['art_key']]),
        'alt': project.get('image_alt') or project['title'],
    }
    return {
        'title': project['title'],
        'project_type': project['project_type'],
        'location': project['location'],
        'description': project['description'],
        'show_on_homepage': True,
        'images': [image],
        'visible_images': [image],
        'hidden_images': [],
        'hidden_image_count': 0,
        'image_url': image['url'],
        'image_alt': image['alt'],
    }


def _public_site_content() -> dict:
    site = (
        PublicSiteSettings.objects
        .prefetch_related('services', 'process_steps', 'project_highlights__gallery_images')
        .filter(singleton=True)
        .first()
    )
    defaults = _public_site_defaults()

    if site is None:
        site = PublicSiteSettings(**defaults)
        services = _default_services()
        process_steps = _default_process_steps()
        project_cards = [_project_card_from_defaults(project) for project in _default_projects()]
    else:
        services = list(site.services.values('title', 'description'))
        process_steps = list(site.process_steps.values('step_label', 'title', 'description'))
        if not services:
            services = _default_services()
        if not process_steps:
            process_steps = _default_process_steps()
        source_items = list(site.project_highlights.all())
        if source_items:
            project_cards = [_project_card_from_model(project) for project in source_items]
        else:
            project_cards = [_project_card_from_defaults(project) for project in _default_projects()]

    firm_profile = FirmProfile.objects.filter(singleton=True).first()
    logo_url = _safe_image_url(getattr(firm_profile, 'logo', None)) or static('img/novart.png')
    hero_image_url = _artwork_url(getattr(site, 'hero_image', None), getattr(site, 'hero_art_key', defaults['hero_art_key']))
    studio_image_url = _artwork_url(getattr(site, 'studio_image', None), getattr(site, 'studio_art_key', defaults['studio_art_key']))
    phone_href = _phone_href(getattr(site, 'phone_display', defaults['phone_display']))
    whatsapp_href = _whatsapp_href(getattr(site, 'whatsapp_number', defaults['whatsapp_number']))

    return {
        'site': site,
        'defaults': defaults,
        'services': services,
        'process_steps': process_steps,
        'project_cards': project_cards,
        'logo_url': logo_url,
        'hero_image_url': hero_image_url,
        'studio_image_url': studio_image_url,
        'phone_href': phone_href,
        'whatsapp_href': whatsapp_href,
    }


def _featured_project_cards(project_cards: list[dict]) -> list[dict]:
    featured_projects = [project for project in project_cards if project.get('show_on_homepage')]
    if featured_projects:
        return featured_projects
    return project_cards[:3]


def _public_nav_links(*, archive: bool = False) -> list[tuple[str, str]]:
    if archive:
        return [
            ('Home', '/'),
            ('Services', '/#services'),
            ('Process', '/#process'),
            ('Selected Work', '/#work'),
            ('Contact', '/#contact'),
        ]
    return [
        ('Services', '#services'),
        ('Process', '#process'),
        ('Selected Work', '#work'),
        ('All Work', '/work/'),
        ('Studio', '#studio'),
        ('Contact', '#contact'),
    ]


def public_home(request):
    content = _public_site_content()
    site = content['site']
    project_cards = content['project_cards']
    homepage_projects = _featured_project_cards(project_cards)

    context = {
        'site': site,
        'logo_url': content['logo_url'],
        'hero_image_url': content['hero_image_url'],
        'studio_image_url': content['studio_image_url'],
        'canonical_url': _canonical_public_url(),
        'og_image_url': _absolute_public_url(content['hero_image_url']),
        'local_business_schema': _local_business_schema(site, content['logo_url'], content['hero_image_url'], project_cards),
        'local_seo_heading': LOCAL_SEO_HEADING,
        'local_seo_body': LOCAL_SEO_BODY,
        'local_service_areas': LOCAL_SERVICE_AREAS,
        'services': content['services'],
        'process_steps': content['process_steps'],
        'projects': homepage_projects,
        'all_project_count': len(project_cards),
        'homepage_project_count': len(homepage_projects),
        'work_archive_url': '/work/',
        'phone_href': content['phone_href'],
        'whatsapp_href': content['whatsapp_href'],
        'section_links': _public_nav_links(),
    }
    return render(request, 'public/home.html', context)


def public_work(request):
    if not is_public_host(request):
        return redirect(_canonical_public_url('/work/'))

    content = _public_site_content()
    site = content['site']
    project_cards = content['project_cards']
    context = {
        'site': site,
        'logo_url': content['logo_url'],
        'canonical_url': _canonical_public_url('/work/'),
        'og_image_url': _absolute_public_url(project_cards[0]['image_url'] if project_cards else content['hero_image_url']),
        'local_business_schema': _local_business_schema(site, content['logo_url'], content['hero_image_url'], project_cards),
        'projects': project_cards,
        'phone_href': content['phone_href'],
        'whatsapp_href': content['whatsapp_href'],
        'section_links': _public_nav_links(archive=True),
    }
    return render(request, 'public/work.html', context)


def site_root(request):
    if is_public_host(request):
        return public_home(request)

    from .views import dashboard

    return dashboard(request)
