document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('is-ready');

    setupNavigation();
    setupSectionSpy();
    setupReveals();
    setupParallax();
    setupMobileFolio();
    setupImageLightbox();
    setupHeroStructure();
});

function setupSectionSpy() {
    const links = [...document.querySelectorAll('.public-nav a')].filter((link) => {
        const href = link.getAttribute('href') || '';
        return href.startsWith('#') && href.length > 1;
    });

    if (!links.length) {
        return;
    }

    const linkBySection = new Map();
    links.forEach((link) => {
        const section = document.getElementById(link.getAttribute('href').slice(1));
        if (section) {
            linkBySection.set(section, link);
        }
    });

    const hero = document.getElementById('top');
    if (hero && !linkBySection.has(hero)) {
        linkBySection.set(hero, null);
    }

    if (!linkBySection.size) {
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            const visible = entries.filter((entry) => entry.isIntersecting);
            if (!visible.length) {
                return;
            }
            const active = linkBySection.get(visible[0].target);
            links.forEach((link) => link.classList.toggle('is-active', link === active));
        },
        { rootMargin: '-42% 0px -52% 0px' }
    );

    linkBySection.forEach((_, section) => observer.observe(section));
}

function setupNavigation() {
    const chrome = document.querySelector('[data-nav]');
    const navToggle = document.querySelector('.public-menu-toggle');
    const nav = document.querySelector('.public-nav');

    const updateChrome = () => {
        if (!chrome) {
            return;
        }
        chrome.classList.toggle('is-scrolled', window.scrollY > 18);
        const scrollable = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
        document.documentElement.style.setProperty('--page-progress', `${clamp(window.scrollY / scrollable, 0, 1)}`);
    };

    updateChrome();
    window.addEventListener('scroll', updateChrome, { passive: true });

    if (!navToggle || !nav) {
        return;
    }

    navToggle.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        navToggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        nav.classList.toggle('is-open', !expanded);
        document.body.classList.toggle('nav-open', !expanded);
        navToggle.textContent = expanded ? 'Menu' : 'Close';
    });

    nav.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => {
            navToggle.setAttribute('aria-expanded', 'false');
            nav.classList.remove('is-open');
            document.body.classList.remove('nav-open');
            navToggle.textContent = 'Menu';
        });
    });
}

function setupReveals() {
    const revealElements = [...document.querySelectorAll('.reveal')];
    if (!revealElements.length) {
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.18, rootMargin: '0px 0px -5% 0px' }
    );

    revealElements.forEach((element) => observer.observe(element));
}

function setupParallax() {
    const parallaxNodes = [...document.querySelectorAll('[data-parallax]')];
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!parallaxNodes.length || reducedMotion) {
        return;
    }

    let ticking = false;

    const renderParallax = () => {
        const viewportHeight = window.innerHeight || 1;

        parallaxNodes.forEach((node) => {
            const speed = Number(node.dataset.parallax || '0.08');
            const rect = node.getBoundingClientRect();
            const centerOffset = rect.top + rect.height / 2 - viewportHeight / 2;
            const shift = centerOffset * speed * -0.35;

            if (node.classList.contains('hero-media')) {
                document.documentElement.style.setProperty('--hero-shift', `${shift}px`);
            } else {
                node.style.transform = `translate3d(0, ${shift}px, 0) scale(1.04)`;
            }
        });

        ticking = false;
    };

    const requestParallax = () => {
        if (!ticking) {
            window.requestAnimationFrame(renderParallax);
            ticking = true;
        }
    };

    renderParallax();
    window.addEventListener('scroll', requestParallax, { passive: true });
    window.addEventListener('resize', requestParallax);
}

function setupMobileFolio() {
    const folio = document.querySelector('.mobile-folio');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!folio || reducedMotion) {
        return;
    }

    let ticking = false;

    const render = () => {
        const rect = folio.getBoundingClientRect();
        const viewportHeight = window.innerHeight || 1;
        const progress = clamp((viewportHeight - rect.top) / (viewportHeight + rect.height), 0, 1);
        const shift = (progress - 0.5) * -26;
        document.documentElement.style.setProperty('--mobile-folio-shift', `${shift}px`);
        ticking = false;
    };

    const requestRender = () => {
        if (!ticking) {
            window.requestAnimationFrame(render);
            ticking = true;
        }
    };

    render();
    window.addEventListener('scroll', requestRender, { passive: true });
    window.addEventListener('resize', requestRender);
}

function setupImageLightbox() {
    const triggers = [...document.querySelectorAll('[data-lightbox-image]')];
    const lightbox = document.querySelector('[data-lightbox]');

    if (!triggers.length || !lightbox) {
        return;
    }

    const image = lightbox.querySelector('[data-lightbox-img]');
    const caption = lightbox.querySelector('[data-lightbox-caption]');
    const count = lightbox.querySelector('[data-lightbox-count]');
    const closeButton = lightbox.querySelector('[data-lightbox-close]');
    const prevButton = lightbox.querySelector('[data-lightbox-prev]');
    const nextButton = lightbox.querySelector('[data-lightbox-next]');
    const zoomInButton = lightbox.querySelector('[data-lightbox-zoom-in]');
    const zoomOutButton = lightbox.querySelector('[data-lightbox-zoom-out]');
    const zoomResetButton = lightbox.querySelector('[data-lightbox-zoom-reset]');
    const items = triggers.map((trigger) => ({
        src: trigger.dataset.lightboxSrc,
        alt: trigger.dataset.lightboxAlt || trigger.querySelector('img')?.alt || 'Project image',
    }));

    let activeIndex = 0;
    let lastFocusedElement = null;
    let scale = 1;
    let offsetX = 0;
    let offsetY = 0;
    let dragStart = null;

    const updateTransform = () => {
        image.style.transform = `translate3d(${offsetX}px, ${offsetY}px, 0) scale(${scale})`;
        lightbox.classList.toggle('is-zoomed', scale > 1);
    };

    const resetZoom = () => {
        scale = 1;
        offsetX = 0;
        offsetY = 0;
        updateTransform();
    };

    const setZoom = (nextScale) => {
        scale = clamp(nextScale, 1, 4);
        if (scale === 1) {
            offsetX = 0;
            offsetY = 0;
        }
        updateTransform();
    };

    const showImage = (nextIndex) => {
        activeIndex = (nextIndex + items.length) % items.length;
        const item = items[activeIndex];
        image.src = item.src;
        image.alt = item.alt;
        caption.textContent = item.alt;
        count.textContent = `${activeIndex + 1} / ${items.length}`;
        resetZoom();
    };

    const openLightbox = (index) => {
        lastFocusedElement = document.activeElement;
        lightbox.hidden = false;
        document.body.classList.add('lightbox-open');
        showImage(index);
        closeButton?.focus({ preventScroll: true });
    };

    const closeLightbox = () => {
        lightbox.hidden = true;
        image.removeAttribute('src');
        document.body.classList.remove('lightbox-open');
        resetZoom();
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus({ preventScroll: true });
        }
    };

    const showPrevious = () => showImage(activeIndex - 1);
    const showNext = () => showImage(activeIndex + 1);

    triggers.forEach((trigger, index) => {
        trigger.addEventListener('click', () => openLightbox(index));
    });

    closeButton?.addEventListener('click', closeLightbox);
    prevButton?.addEventListener('click', showPrevious);
    nextButton?.addEventListener('click', showNext);
    zoomInButton?.addEventListener('click', () => setZoom(scale + 0.35));
    zoomOutButton?.addEventListener('click', () => setZoom(scale - 0.35));
    zoomResetButton?.addEventListener('click', resetZoom);

    image.addEventListener('dblclick', () => {
        setZoom(scale > 1 ? 1 : 2);
    });

    image.addEventListener(
        'wheel',
        (event) => {
            if (lightbox.hidden) {
                return;
            }
            event.preventDefault();
            setZoom(scale + (event.deltaY < 0 ? 0.2 : -0.2));
        },
        { passive: false }
    );

    image.addEventListener('pointerdown', (event) => {
        if (scale <= 1) {
            return;
        }
        dragStart = {
            pointerId: event.pointerId,
            x: event.clientX,
            y: event.clientY,
            offsetX,
            offsetY,
        };
        image.setPointerCapture(event.pointerId);
        lightbox.classList.add('is-dragging');
    });

    image.addEventListener('pointermove', (event) => {
        if (!dragStart || event.pointerId !== dragStart.pointerId) {
            return;
        }
        offsetX = dragStart.offsetX + event.clientX - dragStart.x;
        offsetY = dragStart.offsetY + event.clientY - dragStart.y;
        updateTransform();
    });

    const stopDragging = (event) => {
        if (!dragStart || event.pointerId !== dragStart.pointerId) {
            return;
        }
        dragStart = null;
        lightbox.classList.remove('is-dragging');
    };

    image.addEventListener('pointerup', stopDragging);
    image.addEventListener('pointercancel', stopDragging);

    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) {
            closeLightbox();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (lightbox.hidden) {
            return;
        }

        if (event.key === 'Escape') {
            closeLightbox();
            return;
        }
        if (event.key === 'ArrowLeft') {
            showPrevious();
            return;
        }
        if (event.key === 'ArrowRight') {
            showNext();
            return;
        }
        if (event.key === '+' || event.key === '=') {
            setZoom(scale + 0.35);
            return;
        }
        if (event.key === '-' || event.key === '_') {
            setZoom(scale - 0.35);
            return;
        }
        if (event.key === '0') {
            resetZoom();
        }
    });
}

async function setupHeroStructure() {
    const canvas = document.querySelector('[data-hero-structure]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!canvas || reducedMotion || !hasWebGLSupport()) {
        return;
    }

    let THREE;
    try {
        THREE = await import('https://cdn.jsdelivr.net/npm/three@0.164.1/build/three.module.js');
    } catch (error) {
        canvas.hidden = true;
        return;
    }

    const renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
    });
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 120);
    const cameraBase = new THREE.Vector3(0, 2.05, 10.8);
    const cameraTarget = new THREE.Vector3(1.05, 1.55, 0);

    const group = new THREE.Group();
    scene.add(group);

    const materials = {
        guide: new THREE.LineBasicMaterial({ color: 0xf6f6f2, transparent: true, opacity: 0.13, depthWrite: false }),
        ink: new THREE.LineBasicMaterial({ color: 0xf6f6f2, transparent: true, opacity: 0.55, depthWrite: false }),
        clay: new THREE.LineBasicMaterial({ color: 0xd07a4b, transparent: true, opacity: 0.92, depthWrite: false }),
    };

    const strokes = buildDrawingStages(THREE).map((stage) => {
        const geometry = new THREE.BufferGeometry().setFromPoints(stage.points);
        geometry.setDrawRange(0, 0);
        group.add(new THREE.LineSegments(geometry, materials[stage.material]));
        return { ...stage, geometry, count: stage.points.length };
    });

    const penTip = createPenTip(THREE, group);
    const dust = createDust(THREE, group, window.innerWidth < 761 ? 70 : 130);

    const pointer = { x: 0, y: 0, cx: 0, cy: 0 };
    let scrollProgress = 0;
    let elapsed = 0;
    let lastTime = null;
    let frameId = 0;
    let running = false;
    let inView = true;

    const updatePointer = (event) => {
        pointer.x = (event.clientX / Math.max(window.innerWidth, 1) - 0.5) * 2;
        pointer.y = (event.clientY / Math.max(window.innerHeight, 1) - 0.5) * 2;
    };

    const updateScrollProgress = () => {
        const rect = canvas.getBoundingClientRect();
        scrollProgress = clamp((0 - rect.top) / Math.max(rect.height, 1), 0, 1);
    };

    const resize = () => {
        const width = Math.max(canvas.clientWidth, 1);
        const height = Math.max(canvas.clientHeight, 1);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();

        const aspect = width / height;
        if (aspect < 0.9) {
            group.position.set(0.15, -0.7, 0);
            group.scale.setScalar(0.64);
            cameraBase.set(0, 2.3, 12.9);
            cameraTarget.set(0.1, 1.3, 0);
        } else if (aspect < 1.4) {
            group.position.set(1.15, -0.8, 0);
            group.scale.setScalar(0.82);
            cameraBase.set(0, 2.1, 11.6);
            cameraTarget.set(0.7, 1.45, 0);
        } else {
            group.position.set(2.2, -0.86, 0);
            group.scale.setScalar(0.86);
            cameraBase.set(0, 2.05, 10.8);
            cameraTarget.set(1.2, 1.5, 0);
        }
    };

    const render = (time) => {
        frameId = window.requestAnimationFrame(render);

        if (lastTime === null) {
            lastTime = time;
        }
        const dt = Math.min((time - lastTime) / 1000, 0.05);
        lastTime = time;
        elapsed += dt;

        pointer.cx += (pointer.x - pointer.cx) * 0.055;
        pointer.cy += (pointer.y - pointer.cy) * 0.055;

        let penPoint = null;
        strokes.forEach((stroke) => {
            const raw = (elapsed - stroke.start) / (stroke.end - stroke.start);
            const eased = smoothstep(clamp(raw, 0, 1));
            const target = Math.min(stroke.count, Math.floor((eased * stroke.count) / 2) * 2);
            stroke.geometry.setDrawRange(0, target);
            if (raw > 0 && raw < 1 && target > 0) {
                penPoint = stroke.points[Math.max(target - 1, 0)];
            }
        });

        if (penPoint) {
            penTip.object.position.copy(penPoint);
            penTip.material.opacity = 0.95;
        } else {
            penTip.material.opacity = Math.max(penTip.material.opacity - dt * 1.4, 0);
        }

        updateDust(dust, elapsed, dt);

        const sway = Math.sin(elapsed * 0.22) * 0.045;
        group.rotation.y = -0.52 + sway + pointer.cx * 0.07 + scrollProgress * 0.42;
        group.rotation.x = pointer.cy * 0.028;

        camera.position.set(
            cameraBase.x + pointer.cx * 0.35,
            cameraBase.y + scrollProgress * 3.1 - pointer.cy * 0.22,
            cameraBase.z - scrollProgress * 1.5
        );
        camera.lookAt(cameraTarget);

        renderer.render(scene, camera);
    };

    const start = () => {
        if (!running) {
            running = true;
            lastTime = null;
            frameId = window.requestAnimationFrame(render);
        }
    };

    const stop = () => {
        if (running) {
            running = false;
            window.cancelAnimationFrame(frameId);
        }
    };

    resize();
    updateScrollProgress();
    start();

    window.addEventListener('pointermove', updatePointer, { passive: true });
    window.addEventListener('scroll', updateScrollProgress, { passive: true });
    window.addEventListener('resize', resize);

    if ('ResizeObserver' in window) {
        const resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(canvas);
    }

    if ('IntersectionObserver' in window) {
        const viewObserver = new IntersectionObserver(
            (entries) => {
                inView = entries[0] ? entries[0].isIntersecting : true;
                if (inView && !document.hidden) {
                    start();
                } else {
                    stop();
                }
            },
            { rootMargin: '120px' }
        );
        viewObserver.observe(canvas);
    }

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && inView) {
            start();
        } else {
            stop();
        }
    });
}

/*
 * The hero drawing: a Kerala nalukettu pavilion sketching itself in
 * construction order — guides, plinth, courtyard, columns, beams, then
 * the two-tier hipped roof. Stage timings are seconds from first frame.
 */
function buildDrawingStages(THREE) {
    const W = 3.3; // column grid half-width (x)
    const D = 2.3; // column grid half-depth (z)
    const PLM = 0.5; // plinth margin beyond columns
    const PLY = 0.34; // plinth height
    const LINTEL = 2.62; // column / eave height
    const OV = 0.85; // roof overhang beyond columns
    const TOP_Y = 3.66; // truncated lower-roof top
    const TOP_W = 1.72;
    const TOP_D = 0.88;
    const CLERE_Y = 4.04; // clerestory top / upper eave
    const UP_W = 2.3;
    const UP_D = 1.42;
    const RIDGE_Y = 5.0;
    const RIDGE_HALF = 1.08;
    const CY = 0.84; // courtyard half-size

    const v = (x, y, z) => new THREE.Vector3(x, y, z);
    const seg = (points, ax, ay, az, bx, by, bz) => {
        points.push(v(ax, ay, az), v(bx, by, bz));
    };
    const rect = (points, y, hx, hz) => {
        seg(points, -hx, y, hz, hx, y, hz);
        seg(points, hx, y, hz, hx, y, -hz);
        seg(points, hx, y, -hz, -hx, y, -hz);
        seg(points, -hx, y, -hz, -hx, y, hz);
    };

    const guides = [];
    seg(guides, -6.6, 0, D + PLM + 0.9, 6.6, 0, D + PLM + 0.9);
    seg(guides, -(W + PLM), 0, D + PLM + 0.9, -(W + PLM), 0.22, D + PLM + 0.9);
    seg(guides, W + PLM, 0, D + PLM + 0.9, W + PLM, 0.22, D + PLM + 0.9);
    seg(guides, -5.6, 0, 0, -5.6, 5.6, 0);
    seg(guides, -6.2, RIDGE_Y, 0, 6.2, RIDGE_Y, 0);

    const plinth = [];
    rect(plinth, 0, W + PLM, D + PLM);
    rect(plinth, PLY, W + PLM, D + PLM);
    [-1, 1].forEach((sx) => {
        [-1, 1].forEach((sz) => {
            seg(plinth, sx * (W + PLM), 0, sz * (D + PLM), sx * (W + PLM), PLY, sz * (D + PLM));
        });
    });
    seg(plinth, -1, 0.17, D + PLM + 0.35, 1, 0.17, D + PLM + 0.35);
    seg(plinth, -1, 0.17, D + PLM + 0.35, -1, 0.17, D + PLM);
    seg(plinth, 1, 0.17, D + PLM + 0.35, 1, 0.17, D + PLM);
    seg(plinth, -1, 0, D + PLM + 0.35, -1, 0.17, D + PLM + 0.35);
    seg(plinth, 1, 0, D + PLM + 0.35, 1, 0.17, D + PLM + 0.35);

    const floorGrid = [];
    [-1.9, -0.95, 0, 0.95, 1.9].forEach((z) => {
        seg(floorGrid, -(W + PLM), PLY + 0.01, z, W + PLM, PLY + 0.01, z);
    });
    [-2.85, -1.9, -0.95, 0, 0.95, 1.9, 2.85].forEach((x) => {
        seg(floorGrid, x, PLY + 0.01, -(D + PLM), x, PLY + 0.01, D + PLM);
    });

    const courtyard = [];
    rect(courtyard, PLY + 0.02, CY, CY);
    rect(courtyard, 0.16, CY - 0.2, CY - 0.2);

    const columns = [];
    const columnFeet = [];
    [-W, -1.1, 1.1, W].forEach((x) => {
        columnFeet.push([x, D], [x, -D]);
    });
    columnFeet.push([-W, 0], [W, 0]);
    [-1, 1].forEach((sx) => {
        [-1, 1].forEach((sz) => {
            columnFeet.push([sx * CY, sz * CY]);
        });
    });
    columnFeet.forEach(([x, z]) => {
        seg(columns, x, PLY, z, x, LINTEL, z);
    });

    const beams = [];
    rect(beams, LINTEL, W, D);
    rect(beams, LINTEL, CY, CY);
    [-1, 1].forEach((sx) => {
        seg(beams, sx * CY, LINTEL, CY, sx * 1.1, LINTEL, D);
        seg(beams, sx * CY, LINTEL, -CY, sx * 1.1, LINTEL, -D);
    });

    const roofLower = [];
    const EW = W + OV;
    const ED = D + OV;
    rect(roofLower, LINTEL, EW, ED);
    [-1, 1].forEach((sx) => {
        [-1, 1].forEach((sz) => {
            seg(roofLower, sx * EW, LINTEL, sz * ED, sx * TOP_W, TOP_Y, sz * TOP_D);
        });
    });
    for (let xe = -3.5; xe <= 3.51; xe += 0.7) {
        const xt = (xe / EW) * TOP_W;
        seg(roofLower, xe, LINTEL, ED, xt, TOP_Y, TOP_D);
        seg(roofLower, xe, LINTEL, -ED, xt, TOP_Y, -TOP_D);
    }
    [-1.6, -0.8, 0, 0.8, 1.6].forEach((ze) => {
        const zt = (ze / ED) * TOP_D;
        seg(roofLower, EW, LINTEL, ze, TOP_W, TOP_Y, zt);
        seg(roofLower, -EW, LINTEL, ze, -TOP_W, TOP_Y, zt);
    });

    const topBand = [];
    rect(topBand, TOP_Y, TOP_W, TOP_D);
    [-1, 1].forEach((sx) => {
        [-1, 1].forEach((sz) => {
            seg(topBand, sx * TOP_W, TOP_Y, sz * TOP_D, sx * TOP_W, CLERE_Y, sz * TOP_D);
        });
    });

    const roofUpper = [];
    rect(roofUpper, CLERE_Y, UP_W, UP_D);
    [-1, 1].forEach((sx) => {
        [-1, 1].forEach((sz) => {
            seg(roofUpper, sx * UP_W, CLERE_Y, sz * UP_D, sx * RIDGE_HALF, RIDGE_Y, 0);
        });
    });
    [-1.7, -0.85, 0, 0.85, 1.7].forEach((xe) => {
        const xr = (xe / UP_W) * RIDGE_HALF;
        seg(roofUpper, xe, CLERE_Y, UP_D, xr, RIDGE_Y, 0);
        seg(roofUpper, xe, CLERE_Y, -UP_D, xr, RIDGE_Y, 0);
    });

    const ridge = [];
    seg(ridge, -RIDGE_HALF, RIDGE_Y, 0, RIDGE_HALF, RIDGE_Y, 0);
    seg(ridge, -RIDGE_HALF, RIDGE_Y, 0, -RIDGE_HALF, RIDGE_Y + 0.26, 0);
    seg(ridge, RIDGE_HALF, RIDGE_Y, 0, RIDGE_HALF, RIDGE_Y + 0.26, 0);

    return [
        { material: 'guide', start: 0.0, end: 1.1, points: guides },
        { material: 'ink', start: 0.55, end: 1.75, points: plinth },
        { material: 'guide', start: 0.9, end: 1.9, points: floorGrid },
        { material: 'clay', start: 1.5, end: 2.35, points: courtyard },
        { material: 'ink', start: 1.9, end: 3.15, points: columns },
        { material: 'ink', start: 2.7, end: 3.7, points: beams },
        { material: 'ink', start: 3.2, end: 4.8, points: roofLower },
        { material: 'clay', start: 4.35, end: 5.0, points: topBand },
        { material: 'ink', start: 4.6, end: 5.75, points: roofUpper },
        { material: 'clay', start: 5.5, end: 5.95, points: ridge },
    ];
}

function createPenTip(THREE, group) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0], 3));
    const material = new THREE.PointsMaterial({
        color: 0xe8a271,
        size: 0.14,
        transparent: true,
        opacity: 0,
        depthWrite: false,
    });
    const object = new THREE.Points(geometry, material);
    group.add(object);
    return { object, material };
}

function createDust(THREE, group, count) {
    const positions = new Float32Array(count * 3);
    const baseX = new Float32Array(count);
    const speeds = new Float32Array(count);

    for (let i = 0; i < count; i += 1) {
        baseX[i] = -5 + Math.random() * 10.5;
        positions[i * 3] = baseX[i];
        positions[i * 3 + 1] = Math.random() * 5.8;
        positions[i * 3 + 2] = -3.4 + Math.random() * 6.8;
        speeds[i] = 0.07 + Math.random() * 0.2;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
        color: 0xe9cfae,
        size: 0.05,
        transparent: true,
        opacity: 0,
        depthWrite: false,
    });
    const object = new THREE.Points(geometry, material);
    group.add(object);
    return { object, geometry, material, positions, baseX, speeds, count };
}

function updateDust(dust, elapsed, dt) {
    dust.material.opacity = 0.55 * clamp((elapsed - 4.9) / 1.8, 0, 1);
    if (dust.material.opacity <= 0) {
        return;
    }

    for (let i = 0; i < dust.count; i += 1) {
        let y = dust.positions[i * 3 + 1] + dust.speeds[i] * dt;
        if (y > 5.8) {
            y = 0;
        }
        dust.positions[i * 3 + 1] = y;
        dust.positions[i * 3] = dust.baseX[i] + Math.sin(elapsed * 0.5 + i * 1.7) * 0.14;
    }
    dust.geometry.attributes.position.needsUpdate = true;
}

function smoothstep(t) {
    return t * t * (3 - 2 * t);
}

function hasWebGLSupport() {
    try {
        const probe = document.createElement('canvas');
        return Boolean(probe.getContext('webgl') || probe.getContext('experimental-webgl'));
    } catch (error) {
        return false;
    }
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}
