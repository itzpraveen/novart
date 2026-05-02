document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('is-ready');

    setupNavigation();
    setupReveals();
    setupParallax();
    setupMobileFolio();
    setupHeroStructure();
});

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
        preserveDrawingBuffer: true,
        powerPreference: 'high-performance',
    });
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(1.15, 1.2, 8.4);

    const group = new THREE.Group();
    group.position.set(1.35, -0.62, 0);
    scene.add(group);

    const lineMaterial = new THREE.LineBasicMaterial({
        color: 0xf6f6f2,
        transparent: true,
        opacity: 0.24,
        depthWrite: false,
    });
    const accentMaterial = new THREE.LineBasicMaterial({
        color: 0xa95735,
        transparent: true,
        opacity: 0.48,
        depthWrite: false,
    });

    addLineSegments(THREE, group, buildFloorGrid(THREE), lineMaterial);
    addLineSegments(THREE, group, buildRoomFrame(THREE), lineMaterial);
    addLineSegments(THREE, group, buildVerticalRhythm(THREE), accentMaterial);
    addPointCloud(THREE, group);

    const pointer = { x: 0, y: 0 };
    let scrollProgress = 0;
    let frameId = 0;

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
    };

    const render = (time = 0) => {
        const seconds = time * 0.001;
        group.rotation.x = -0.18 + pointer.y * 0.035;
        group.rotation.y = -0.22 + Math.sin(seconds * 0.48) * 0.065 + pointer.x * 0.08;
        group.position.x = 1.35 + pointer.x * 0.12;
        group.position.y = -0.62 + scrollProgress * 0.36 + Math.sin(seconds * 0.3) * 0.06;
        camera.position.z = 8.4 - scrollProgress * 0.28;
        renderer.render(scene, camera);
        frameId = window.requestAnimationFrame(render);
    };

    resize();
    updateScrollProgress();
    render();

    window.addEventListener('pointermove', updatePointer, { passive: true });
    window.addEventListener('scroll', updateScrollProgress, { passive: true });
    window.addEventListener('resize', resize);

    if ('ResizeObserver' in window) {
        const resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(canvas);
    }

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            window.cancelAnimationFrame(frameId);
        } else {
            render();
        }
    });
}

function hasWebGLSupport() {
    try {
        const probe = document.createElement('canvas');
        return Boolean(probe.getContext('webgl') || probe.getContext('experimental-webgl'));
    } catch (error) {
        return false;
    }
}

function addLineSegments(THREE, group, points, material) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const lines = new THREE.LineSegments(geometry, material);
    group.add(lines);
}

function buildFloorGrid(THREE) {
    const points = [];
    const size = 4.2;

    for (let index = -4; index <= 4; index += 1) {
        const offset = index * 0.72;
        points.push(new THREE.Vector3(-size, 0, offset), new THREE.Vector3(size, 0, offset));
        points.push(new THREE.Vector3(offset, 0, -size), new THREE.Vector3(offset, 0, size));
    }

    return points;
}

function buildRoomFrame(THREE) {
    const points = [];
    const x = 4.2;
    const y = 2.85;
    const z = 3.1;
    const corners = [
        [-x, 0, -z],
        [x, 0, -z],
        [x, 0, z],
        [-x, 0, z],
        [-x, y, -z],
        [x, y, -z],
        [x, y, z],
        [-x, y, z],
    ].map(([cx, cy, cz]) => new THREE.Vector3(cx, cy, cz));

    const edges = [
        [0, 1],
        [1, 2],
        [2, 3],
        [3, 0],
        [4, 5],
        [5, 6],
        [6, 7],
        [7, 4],
        [0, 4],
        [1, 5],
        [2, 6],
        [3, 7],
    ];

    edges.forEach(([start, end]) => {
        points.push(corners[start], corners[end]);
    });

    return points;
}

function buildVerticalRhythm(THREE) {
    const points = [];
    const z = 3.1;

    for (let index = -3; index <= 3; index += 1) {
        const x = index * 1.12;
        points.push(new THREE.Vector3(x, 0, -z), new THREE.Vector3(x, 2.85, -z));
        points.push(new THREE.Vector3(x, 0, z), new THREE.Vector3(x, 2.85, z));
    }

    return points;
}

function addPointCloud(THREE, group) {
    const positions = [];

    for (let x = -3; x <= 3; x += 1) {
        for (let z = -3; z <= 3; z += 1) {
            if ((x + z) % 2 === 0) {
                positions.push(x * 0.9, 0.02, z * 0.9);
            }
        }
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
        color: 0xf6f6f2,
        size: 0.035,
        transparent: true,
        opacity: 0.52,
        depthWrite: false,
    });
    group.add(new THREE.Points(geometry, material));
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}
