const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

setupHeader();
setupNavigation();
setupSunStudy();
setupHoverViews();
setupFilters();
setupLightbox();
setupVideo();

function setupHeader() {
    const header = document.querySelector('[data-header]');
    const actionBar = document.querySelector('[data-action-bar]');
    const hero = document.querySelector('[data-hero]');

    const update = () => {
        header?.classList.toggle('is-scrolled', window.scrollY > 8);
        if (actionBar && hero) {
            actionBar.classList.toggle('is-visible', hero.getBoundingClientRect().bottom < window.innerHeight * 0.4);
        }
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
}

function setupNavigation() {
    const header = document.querySelector('[data-header]');
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.getElementById('site-nav');
    if (!toggle || !nav) {
        return;
    }

    if (location.pathname.startsWith('/work/')) {
        nav.querySelector('a[href="/work/"]')?.setAttribute('aria-current', 'page');
    }

    const setOpen = (open) => {
        toggle.setAttribute('aria-expanded', String(open));
        toggle.textContent = open ? 'Close' : 'Menu';
        nav.classList.toggle('is-open', open);
        header?.classList.toggle('has-open-nav', open);
    };

    toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
    nav.addEventListener('click', (event) => {
        if (event.target.closest('a')) {
            setOpen(false);
        }
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && nav.classList.contains('is-open')) {
            setOpen(false);
            toggle.focus();
        }
    });
}

function setupSunStudy() {
    const stage = document.querySelector('[data-sun-study]');
    if (!stage || !hasWebGL()) {
        return;
    }

    const start = () => {
        import(stage.dataset.module)
            .then((module) => module.mount(stage, { reducedMotion: reducedMotion.matches }))
            .catch((error) => console.warn('Sun study unavailable:', error));
    };

    const whenIdle = () => ('requestIdleCallback' in window ? requestIdleCallback(start, { timeout: 1500 }) : setTimeout(start, 200));
    if (document.readyState === 'complete') {
        whenIdle();
    } else {
        window.addEventListener('load', whenIdle, { once: true });
    }
}

function hasWebGL() {
    try {
        const canvas = document.createElement('canvas');
        return Boolean(window.WebGL2RenderingContext && canvas.getContext('webgl2'));
    } catch {
        return false;
    }
}

function setupHoverViews() {
    if (!window.matchMedia('(hover: hover)').matches) {
        return;
    }
    document.querySelectorAll('.work-card__link').forEach((link) => {
        const alt = link.querySelector('img[data-srcset]');
        if (!alt) {
            return;
        }
        link.addEventListener('pointerenter', () => {
            if (!alt.srcset) {
                alt.srcset = alt.dataset.srcset;
            }
        }, { once: true });
    });
}

function setupFilters() {
    const group = document.querySelector('[data-filters]');
    const grid = document.querySelector('[data-archive]');
    if (!group || !grid) {
        return;
    }

    const buttons = [...group.querySelectorAll('[data-filter]')];
    const cards = [...grid.querySelectorAll('[data-type]')];
    const empty = document.querySelector('[data-archive-empty]');

    const apply = (key, updateUrl) => {
        const valid = buttons.some((button) => button.dataset.filter === key);
        const active = valid ? key : 'all';
        buttons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.filter === active)));
        let shown = 0;
        cards.forEach((card) => {
            const visible = active === 'all' || card.dataset.type === active;
            card.hidden = !visible;
            shown += visible ? 1 : 0;
        });
        if (empty) {
            empty.hidden = shown > 0;
        }
        if (updateUrl) {
            const url = new URL(location.href);
            if (active === 'all') {
                url.searchParams.delete('type');
            } else {
                url.searchParams.set('type', active);
            }
            history.replaceState(null, '', url);
        }
    };

    group.addEventListener('click', (event) => {
        const button = event.target.closest('[data-filter]');
        if (button) {
            apply(button.dataset.filter, true);
        }
    });

    const initial = new URLSearchParams(location.search).get('type');
    if (initial) {
        apply(initial, false);
    }
}

function setupLightbox() {
    const dialog = document.querySelector('[data-lightbox-dialog]');
    const items = [...document.querySelectorAll('[data-lightbox]')];
    if (!dialog || !items.length || typeof dialog.showModal !== 'function') {
        return;
    }

    const image = dialog.querySelector('[data-lightbox-image]');
    const caption = dialog.querySelector('[data-lightbox-caption]');
    let index = 0;

    const show = (next) => {
        index = (next + items.length) % items.length;
        const item = items[index];
        const thumb = item.querySelector('img');
        image.src = item.dataset.full;
        image.alt = thumb?.alt || '';
        image.width = Number(item.dataset.width) || 0;
        image.height = Number(item.dataset.height) || 0;
        caption.textContent = `${index + 1} of ${items.length}`;
        [index - 1, index + 1].forEach((n) => {
            const neighbour = items[(n + items.length) % items.length];
            new Image().src = neighbour.dataset.full;
        });
    };

    items.forEach((item, i) => {
        item.addEventListener('click', () => {
            show(i);
            dialog.showModal();
        });
    });

    dialog.querySelector('[data-lightbox-prev]').addEventListener('click', () => show(index - 1));
    dialog.querySelector('[data-lightbox-next]').addEventListener('click', () => show(index + 1));
    dialog.querySelector('[data-lightbox-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => items[index].focus());
    dialog.addEventListener('click', (event) => {
        if (event.target === dialog || event.target.classList.contains('lightbox__figure')) {
            dialog.close();
        }
    });
    dialog.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowLeft') {
            show(index - 1);
        } else if (event.key === 'ArrowRight') {
            show(index + 1);
        }
    });

    let touchX = null;
    dialog.addEventListener('touchstart', (event) => {
        touchX = event.touches[0].clientX;
    }, { passive: true });
    dialog.addEventListener('touchend', (event) => {
        if (touchX === null) {
            return;
        }
        const dx = event.changedTouches[0].clientX - touchX;
        touchX = null;
        if (Math.abs(dx) > 48) {
            show(index + (dx < 0 ? 1 : -1));
        }
    });
}

function setupVideo() {
    document.querySelectorAll('[data-video]').forEach((frame) => {
        const button = frame.querySelector('.video__play');
        button?.addEventListener('click', () => {
            const iframe = document.createElement('iframe');
            iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(frame.dataset.video)}?autoplay=1&rel=0`;
            iframe.title = 'Project walkthrough video';
            iframe.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen';
            iframe.allowFullscreen = true;
            frame.replaceChildren(iframe);
            iframe.focus();
        });
    });
}
