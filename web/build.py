#!/usr/bin/env python3
"""Build the static Novart Architects website.

    python3 web/build.py            # writes ./site
    python3 web/build.py --out dist

Content lives in web/content/*.json, photos in web/media/, CSS/JS/vendor
files in web/static/. Requires Pillow for the responsive image variants.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
WIDTHS = (480, 960, 1600)
TYPE_LABELS = {'New home': 'New homes', 'Renovation': 'Renovations'}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


class Images:
    """Resizes each photo once into WebP variants and copies the original."""

    def __init__(self, out: Path):
        self.out = out
        self.info = {}

    def get(self, name: str) -> dict:
        if name in self.info:
            return self.info[name]
        src = ROOT / 'media' / name
        stem = slugify(Path(name).stem)
        variants = []
        with Image.open(src) as opened:
            image = ImageOps.exif_transpose(opened).convert('RGB')
        width, height = image.size
        for target in WIDTHS:
            actual = min(target, width)
            dest = self.out / 'media' / str(target) / f'{stem}.webp'
            if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
                dest.parent.mkdir(parents=True, exist_ok=True)
                resized = image if actual == width else image.resize(
                    (actual, round(height * actual / width)), Image.LANCZOS
                )
                resized.save(dest, 'WEBP', quality=80, method=4)
            variants.append((actual, f'/media/{target}/{stem}.webp'))
            if actual == width:
                break
        original = self.out / 'media' / 'public_site' / name
        if not original.exists():
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, original)
        self.info[name] = {
            'width': width,
            'height': height,
            'variants': variants,
            'large': variants[-1][1],
            'original': f'/media/public_site/{quote(name)}',
        }
        return self.info[name]

    def tag(self, name, alt, sizes, cls='', eager=False, extra=''):
        info = self.get(name)
        srcset = ', '.join(f'{url} {w}w' for w, url in info['variants'])
        default = info['variants'][min(1, len(info['variants']) - 1)][1]
        loading = 'eager" fetchpriority="high' if eager else 'lazy'
        class_attr = f' class="{cls}"' if cls else ''
        return (
            f'<img{class_attr} src="{default}" srcset="{srcset}" sizes="{sizes}" '
            f'width="{info["width"]}" height="{info["height"]}" alt="{esc(alt)}" '
            f'loading="{loading}" decoding="async"{extra}>'
        )


class Site:
    def __init__(self, out: Path):
        self.out = out
        self.data = json.loads((ROOT / 'content' / 'site.json').read_text())
        self.projects = json.loads((ROOT / 'content' / 'projects.json').read_text())
        self.images = Images(out)
        self.hashes = {}

    # ----- helpers ---------------------------------------------------------

    def asset(self, path: str) -> str:
        if path not in self.hashes:
            digest = hashlib.sha1((ROOT / 'static' / path).read_bytes()).hexdigest()[:10]
            self.hashes[path] = digest
        return f'/static/{path}?v={self.hashes[path]}'

    def whatsapp(self, message=None) -> str:
        text = message or self.data['whatsapp_message']
        return f"https://wa.me/{self.data['whatsapp']}?text={quote(text)}"

    def absolute(self, path: str) -> str:
        return self.data['url'] + path

    def project_url(self, project) -> str:
        return f"/work/{project['slug']}/"

    def project_meta(self, project) -> str:
        return f"{project['type']} in {project['place']}"

    def gallery_images(self, project):
        return [image for image in project['images'] if not image.get('before')]

    def schema(self) -> str:
        d = self.data
        cover = self.images.get(self.projects[0]['images'][0]['file'])['original']
        schema = {
            '@context': 'https://schema.org',
            '@type': ['LocalBusiness', 'ArchitecturalService'],
            '@id': f"{d['url']}/#studio",
            'name': d['name'],
            'url': f"{d['url']}/",
            'logo': self.absolute('/static/img/novart-logo.png'),
            'image': [self.absolute(cover)],
            'description': d['meta_description'],
            'telephone': d['phone_display'],
            'email': d['email'],
            'priceRange': 'Contact for quote',
            'address': {
                '@type': 'PostalAddress',
                'streetAddress': d['address'][0],
                'addressLocality': 'Edavannapara',
                'addressRegion': 'Kerala',
                'postalCode': '673645',
                'addressCountry': 'IN',
            },
            'geo': {'@type': 'GeoCoordinates', 'latitude': d['latitude'], 'longitude': d['longitude']},
            'areaServed': [{'@type': 'Place', 'name': area} for area in d['areas']],
        }
        return json.dumps(schema, ensure_ascii=False, separators=(',', ':'))

    # ----- shared chrome ---------------------------------------------------

    def layout(self, *, path, title, description, body, body_class, og_image, head_extra='', noindex=False):
        d = self.data
        canonical = self.absolute(path)
        robots = 'noindex' if noindex else 'index,follow,max-image-preview:large'
        return f'''<!DOCTYPE html>
<html lang="en-IN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(description)}">
    <link rel="canonical" href="{canonical}">
    <meta name="robots" content="{robots}">
    <meta name="theme-color" content="#edece7">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="{esc(d['name'])}">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(description)}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{self.absolute(og_image)}">
    <meta property="og:locale" content="en_IN">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="icon" href="/favicon.ico">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&amp;display=swap">
    <link rel="stylesheet" href="{self.asset('css/site.css')}">
{head_extra}    <script type="application/ld+json">{self.schema()}</script>
</head>
<body class="{body_class}">
    <a class="skip-link" href="#main">Skip to content</a>
{self.header()}
    <main id="main">
{body}
    </main>
{self.footer()}
{self.action_bar()}
    <script type="module" src="{self.asset('js/site.js')}"></script>
</body>
</html>
'''

    def header(self) -> str:
        return f'''    <header class="site-header" data-header>
        <a class="brand" href="/" aria-label="{esc(self.data['name'])}, home"><span class="brand__logo" aria-hidden="true"></span></a>
        <nav class="site-nav" id="site-nav" aria-label="Main">
            <a href="/work/">Work</a>
            <a href="/#services">Services</a>
            <a href="/#studio">Studio</a>
            <a href="/#contact">Contact</a>
        </nav>
        <a class="button button--small button--primary site-header__cta" href="{self.whatsapp()}" target="_blank" rel="noopener">WhatsApp us</a>
        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
    </header>'''

    def footer(self) -> str:
        d = self.data
        address = '<br>'.join(esc(line) for line in d['address'])
        return f'''    <footer class="site-footer">
        <div class="site-footer__inner">
            <div class="site-footer__brand">
                <span class="brand__logo" aria-hidden="true"></span>
                <p>Architecture, interiors and renovation in Malappuram and Kozhikode.</p>
            </div>
            <nav class="site-footer__nav" aria-label="Footer">
                <a href="/work/">Work</a>
                <a href="/#services">Services</a>
                <a href="/#process">Process</a>
                <a href="/#studio">Studio</a>
            </nav>
            <address class="site-footer__contact">
                <a href="tel:{d['phone']}">{esc(d['phone_display'])}</a><br>
                <a href="mailto:{d['email']}">{esc(d['email'])}</a><br>
                {address}
            </address>
        </div>
        <p class="site-footer__legal">&copy; {date.today().year} {esc(d['name'])}</p>
    </footer>'''

    def action_bar(self) -> str:
        return f'''    <div class="action-bar" data-action-bar>
        <a class="button button--primary" href="{self.whatsapp()}" target="_blank" rel="noopener">WhatsApp</a>
        <a class="button button--outline" href="tel:{self.data['phone']}">Call</a>
    </div>'''

    def contact_band(self) -> str:
        d = self.data
        return f'''        <section class="contact" id="contact" aria-labelledby="contact-title">
            <div class="contact__inner">
                <h2 id="contact-title">{esc(d['contact']['title'])}</h2>
                <p class="contact__text">{esc(d['contact']['text'])}</p>
                <div class="contact__actions">
                    <a class="button button--light" href="{self.whatsapp()}" target="_blank" rel="noopener">Message us on WhatsApp</a>
                    <a class="button button--outline-light" href="tel:{d['phone']}">Call {esc(d['phone_display'])}</a>
                </div>
                <p class="contact__email">Or email <a href="mailto:{d['email']}">{esc(d['email'])}</a></p>
            </div>
        </section>'''

    def work_card(self, project, *, lead=False, heading='h3') -> str:
        images = self.gallery_images(project)
        cover = images[0]['file']
        sizes = '(max-width: 760px) 100vw, 50vw'
        alt_view = ''
        if len(images) > 1:
            # Second view for hover; site.js sets srcset only on devices that can hover.
            alt = self.images.get(images[1]['file'])
            srcset = ', '.join(f'{url} {w}w' for w, url in alt['variants'])
            alt_view = (
                f'<img class="work-card__alt" data-srcset="{srcset}" sizes="{sizes}" '
                f'width="{alt["width"]}" height="{alt["height"]}" alt="" aria-hidden="true" decoding="async">'
            )
        lead_class = ' work-card--lead' if lead else ''
        return f'''                <article class="work-card{lead_class}" data-type="{slugify(project['type'])}">
                    <a class="work-card__link" href="{self.project_url(project)}">
                        <div class="work-card__media">
                            {self.images.tag(cover, project['title'], sizes, cls='work-card__cover')}
                            {alt_view}
                        </div>
                        <div class="work-card__text">
                            <{heading} class="work-card__title">{esc(project['title'])}</{heading}>
                            <p class="work-card__meta">{esc(self.project_meta(project))}<span>{len(images)} photos</span></p>
                            <p class="work-card__summary">{esc(project['summary'])}</p>
                        </div>
                    </a>
                </article>'''

    # ----- pages -----------------------------------------------------------

    def home(self) -> str:
        d = self.data
        hero = d['hero']
        services = '\n'.join(
            f'''                    <div class="service">
                        <dt>{esc(s['title'])}</dt>
                        <dd>{esc(s['text'])}</dd>
                    </div>'''
            for s in d['services']
        )
        steps = '\n'.join(
            f'''                    <li class="step">
                        <span class="step__number" aria-hidden="true">{i}</span>
                        <h3>{esc(s['title'])}</h3>
                        <p>{esc(s['text'])}</p>
                    </li>'''
            for i, s in enumerate(d['process'], start=1)
        )
        cards = '\n'.join(self.work_card(p, lead=(i == 0)) for i, p in enumerate(self.projects))
        studio = d['studio']
        studio_text = '\n'.join(f'                    <p>{esc(t)}</p>' for t in studio['text'])
        areas = ', '.join(d['areas'][:-1]) + f" and {d['areas'][-1]}"
        address = '<br>'.join(esc(line) for line in d['address'])
        body = f'''        <section class="hero" data-hero aria-labelledby="hero-title">
            <div class="hero__stage" data-sun-study data-module="{self.asset('js/sun-study.js')}" data-lat="{d['latitude']}" data-lon="{d['longitude']}">
                <picture class="hero__poster">
                    <source media="(max-aspect-ratio: 4/5)" srcset="/static/img/sun-study-tall.webp">
                    <img src="/static/img/sun-study-wide.webp" alt="" width="1600" height="1000" fetchpriority="high">
                </picture>
                <canvas class="hero__canvas" aria-hidden="true"></canvas>
            </div>
            <div class="hero__copy">
                <h1 id="hero-title">{esc(hero['title'])}</h1>
                <p>{esc(hero['text'])}</p>
                <div class="hero__actions">
                    <a class="button button--primary" href="{self.whatsapp()}" target="_blank" rel="noopener">Message us on WhatsApp</a>
                    <a class="button button--outline" href="#work">See our homes</a>
                </div>
            </div>
            <div class="sun-dial" data-sun-dial hidden>
                <div class="sun-dial__readout">
                    <label for="sun-time">Drag to move the sun</label>
                    <output for="sun-time" data-sun-clock></output>
                    <span data-sun-altitude></span>
                </div>
                <div class="sun-dial__track">
                    <input class="sun-dial__range" type="range" id="sun-time" min="330" max="1170" step="1" value="990">
                    <div class="sun-dial__scale" aria-hidden="true" data-sun-scale></div>
                </div>
            </div>
        </section>

        <section class="work" id="work" aria-labelledby="work-title">
            <div class="section-head">
                <h2 id="work-title">Homes we've designed</h2>
                <p>New homes and renovations across Malappuram district, photographed after handover.</p>
                <a class="text-link" href="/work/">All projects</a>
            </div>
            <div class="work-grid">
{cards}
            </div>
        </section>

        <section class="practice" id="services" aria-labelledby="services-title">
            <div class="practice__intro">
                <h2 id="services-title">What we do</h2>
                <p>One studio from the first site visit to the day you move in.</p>
            </div>
            <dl class="services">
{services}
            </dl>
        </section>

        <section class="process" id="process" aria-labelledby="process-title">
            <h2 id="process-title">How a project runs</h2>
            <ol class="steps">
{steps}
            </ol>
        </section>

        <section class="studio" id="studio" aria-labelledby="studio-title">
            <figure class="studio__media">
                {self.images.tag(studio['image'], studio['image_alt'], '(max-width: 760px) 100vw, 40vw')}
            </figure>
            <div class="studio__text">
                <h2 id="studio-title">{esc(studio['title'])}</h2>
{studio_text}
                <p>We work with families in {esc(areas)}.</p>
                <div class="studio__visit">
                    <h3>Visit the studio</h3>
                    <address>{address}</address>
                    <a class="text-link" href="{d['map_url']}" target="_blank" rel="noopener">Get directions</a>
                </div>
            </div>
        </section>

{self.contact_band()}'''
        head_extra = (
            '    <script type="importmap">{"imports":{"three":"/static/vendor/three-0.170.0/three.module.min.js",'
            '"three/addons/":"/static/vendor/three-0.170.0/addons/"}}</script>\n'
            '    <link rel="preload" as="image" href="/static/img/sun-study-wide.webp" media="(min-aspect-ratio: 4/5)">\n'
        )
        cover = self.images.get(self.projects[0]['images'][0]['file'])['original']
        return self.layout(
            path='/', title=d['meta_title'], description=d['meta_description'], body=body,
            body_class='page-home', og_image=cover, head_extra=head_extra,
        )

    def work_index(self) -> str:
        counts = {}
        for p in self.projects:
            counts[p['type']] = counts.get(p['type'], 0) + 1
        filters = [f'<button type="button" class="filter" data-filter="all" aria-pressed="true">All <span>{len(self.projects)}</span></button>']
        for kind, count in counts.items():
            label = TYPE_LABELS.get(kind, kind)
            filters.append(
                f'<button type="button" class="filter" data-filter="{slugify(kind)}" aria-pressed="false">{esc(label)} <span>{count}</span></button>'
            )
        cards = '\n'.join(self.work_card(p, heading='h2') for p in self.projects)
        total = sum(len(self.gallery_images(p)) for p in self.projects)
        body = f'''        <section class="page-head">
            <h1>Our work</h1>
            <p>{len(self.projects)} homes and {total} photos from projects across Malappuram district. Open a project to see every room.</p>
            <div class="filters" role="group" aria-label="Show projects by type" data-filters>
                {' '.join(filters)}
            </div>
        </section>
        <section class="archive" aria-label="Projects">
            <div class="archive-grid" data-archive>
{cards}
            </div>
            <p class="archive__empty" data-archive-empty hidden>No projects of this type yet.</p>
        </section>

{self.contact_band()}'''
        cover = self.images.get(self.projects[0]['images'][0]['file'])['original']
        return self.layout(
            path='/work/', title=f"Our work | {self.data['name']}",
            description=f"New homes and renovations by {self.data['name']} in Malappuram district, Kerala.",
            body=body, body_class='page-work', og_image=cover,
        )

    def project_page(self, project, previous, following) -> str:
        images = self.gallery_images(project)
        cover = images[0]['file']
        before = next((i for i in project['images'] if i.get('before')), None)
        facts = [['Type', project['type']], ['Location', project['place']], *project['facts'], ['Photos', str(len(images))]]
        facts_html = '\n'.join(
            f'                    <div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts
        )
        story = '\n'.join(f'                <p>{esc(p)}</p>' for p in project['story'])
        message = f"Hi Novart Architects, I saw {project['title']} on your website and would like to discuss a similar project."

        before_html = ''
        if before:
            before_html = f'''
            <section class="compare" aria-labelledby="compare-title">
                <h2 id="compare-title">Before and after</h2>
                <div class="compare__pair">
                    <figure>
                        {self.images.tag(before['file'], f"{project['title']} before renovation", '(max-width: 760px) 100vw, 50vw')}
                        <figcaption>Before</figcaption>
                    </figure>
                    <figure>
                        {self.images.tag(cover, f"{project['title']} after renovation", '(max-width: 760px) 100vw, 50vw')}
                        <figcaption>After</figcaption>
                    </figure>
                </div>
            </section>'''

        video_html = ''
        video_id = project['youtube'].rstrip('/').rsplit('/', 1)[-1] if project['youtube'] else ''
        if video_id:
            poster = images[1]['file'] if len(images) > 1 else cover
            video_html = f'''
            <section class="video" aria-labelledby="video-title">
                <h2 id="video-title">Walkthrough video</h2>
                <div class="video__frame" data-video="{esc(video_id)}">
                    {self.images.tag(poster, '', '(max-width: 760px) 100vw, 80vw', cls='video__poster')}
                    <button class="video__play" type="button"><span class="video__icon" aria-hidden="true"></span>Play the walkthrough</button>
                </div>
                <p><a class="text-link" href="https://www.youtube.com/watch?v={esc(video_id)}" target="_blank" rel="noopener">Watch on YouTube</a></p>
            </section>'''

        tiles = []
        for index, image in enumerate(images):
            info = self.images.get(image['file'])
            alt = f"{project['title']}, photo {index + 1} of {len(images)}"
            tiles.append(
                f'''                    <button class="gallery__item" type="button" data-lightbox="{index}" data-full="{info['large']}" data-width="{info['width']}" data-height="{info['height']}" aria-label="Open photo {index + 1} of {len(images)}">
                        {self.images.tag(image['file'], alt, '(max-width: 760px) 50vw, 33vw')}
                    </button>'''
            )
        tiles_html = '\n'.join(tiles)

        pager = f'''            <nav class="pager" aria-label="More projects">
                <a class="pager__link" href="{self.project_url(previous)}" rel="prev"><span>Previous project</span>{esc(previous['title'])}</a>
                <a class="pager__link pager__link--next" href="{self.project_url(following)}" rel="next"><span>Next project</span>{esc(following['title'])}</a>
            </nav>'''

        body = f'''        <article class="project">
            <header class="project-head">
                <a class="back-link" href="/work/">All projects</a>
                <h1>{esc(project['title'])}</h1>
                <p class="project-head__summary">{esc(project['summary'])}</p>
                <dl class="facts">
{facts_html}
                </dl>
                <div class="project-head__actions">
                    <a class="button button--primary" href="{self.whatsapp(message)}" target="_blank" rel="noopener">Ask about a similar home</a>
                    <a class="button button--outline" href="tel:{self.data['phone']}">Call the studio</a>
                </div>
            </header>
            <figure class="project-cover">
                {self.images.tag(cover, project['title'], '100vw', eager=True)}
            </figure>
            <section class="project-story" aria-label="About the project">
{story}
            </section>{before_html}{video_html}
            <section class="gallery" aria-labelledby="gallery-title">
                <h2 id="gallery-title">Photos</h2>
                <div class="gallery__grid" data-gallery>
{tiles_html}
                </div>
            </section>
{pager}
        </article>
{self.lightbox()}

{self.contact_band()}'''
        return self.layout(
            path=self.project_url(project),
            title=f"{project['title']} | {self.project_meta(project)} | {self.data['name']}",
            description=project['summary'], body=body, body_class='page-project',
            og_image=self.images.get(cover)['original'],
        )

    def lightbox(self) -> str:
        return '''        <dialog class="lightbox" data-lightbox-dialog aria-label="Photo viewer">
            <figure class="lightbox__figure">
                <img class="lightbox__image" alt="" data-lightbox-image>
                <figcaption class="lightbox__caption" data-lightbox-caption></figcaption>
            </figure>
            <button class="lightbox__button lightbox__button--prev" type="button" data-lightbox-prev>Previous photo</button>
            <button class="lightbox__button lightbox__button--next" type="button" data-lightbox-next>Next photo</button>
            <button class="lightbox__close" type="button" data-lightbox-close>Close</button>
        </dialog>'''

    def not_found(self) -> str:
        body = f'''        <section class="page-head page-head--center">
            <h1>This page doesn't exist</h1>
            <p>The link may be old or mistyped. Our projects are all on the work page.</p>
            <div class="hero__actions">
                <a class="button button--primary" href="/work/">See our work</a>
                <a class="button button--outline" href="/">Go to the home page</a>
            </div>
        </section>'''
        cover = self.images.get(self.projects[0]['images'][0]['file'])['original']
        return self.layout(
            path='/404.html', title=f"Page not found | {self.data['name']}",
            description=self.data['meta_description'], body=body, body_class='page-404',
            og_image=cover, noindex=True,
        )

    # ----- output ----------------------------------------------------------

    def write(self, path: str, text: str):
        dest = self.out / path.lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    def build(self):
        shutil.copytree(ROOT / 'static', self.out / 'static', dirs_exist_ok=True)
        shutil.copy2(ROOT / 'static' / 'favicon.ico', self.out / 'favicon.ico')
        self.write('/index.html', self.home())
        self.write('/work/index.html', self.work_index())
        count = len(self.projects)
        for i, project in enumerate(self.projects):
            previous = self.projects[(i - 1) % count]
            following = self.projects[(i + 1) % count]
            self.write(f"/work/{project['slug']}/index.html", self.project_page(project, previous, following))
        self.write('/404.html', self.not_found())
        urls = ['/', '/work/'] + [self.project_url(p) for p in self.projects]
        entries = '\n'.join(f'  <url><loc>{self.absolute(u)}</loc></url>' for u in urls)
        self.write('/sitemap.xml', f'<?xml version="1.0" encoding="UTF-8"?>\n'
                   f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n')
        self.write('/robots.txt', f"User-agent: *\nAllow: /\nSitemap: {self.absolute('/sitemap.xml')}\n")
        print(f'Built {len(urls)} pages and {len(self.images.info)} photos into {self.out}')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', default=str(ROOT.parent / 'site'))
    args = parser.parse_args()
    out = Path(args.out).resolve()
    for stale in ('index.html', 'work', 'static', '404.html'):
        target = out / stale
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    out.mkdir(parents=True, exist_ok=True)
    Site(out).build()


if __name__ == '__main__':
    main()
