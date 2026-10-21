// Sun study: a study model of a contemporary Kerala house lit by the real sun
// path over the studio for today's date. The slider moves the time of day.
//
// Scene axes: +x north, -x south, +z east (the house front), y up, 1 unit = 1 m.

import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/RoomEnvironment.js';
import { mergeGeometries } from 'three/addons/BufferGeometryUtils.js';

const RAD = Math.PI / 180;
const IST_MERIDIAN = 82.5;

// Backdrop and light keyed by sun altitude (degrees).
const LIGHT_KEYS = [
    { alt: -12, top: '#111827', bottom: '#212a3f', sun: '#ff7a3d', sunI: 0, sky: '#34446a', ground: '#1b1f29', hemiI: 0.32, env: 0.1, glow: 1 },
    { alt: -4, top: '#28304f', bottom: '#86687a', sun: '#ff7a3d', sunI: 0, sky: '#5a668e', ground: '#3b3237', hemiI: 0.42, env: 0.16, glow: 0.9 },
    { alt: 0, top: '#5c6f93', bottom: '#dc9c78', sun: '#ff8a4a', sunI: 0.7, sky: '#8796bb', ground: '#6a5446', hemiI: 0.55, env: 0.22, glow: 0.45 },
    { alt: 6, top: '#98adc2', bottom: '#eec39b', sun: '#ffa862', sunI: 2.9, sky: '#b7c4d6', ground: '#8a6f58', hemiI: 0.5, env: 0.18, glow: 0.08 },
    { alt: 20, top: '#b9cad4', bottom: '#eee1cf', sun: '#ffdcb2', sunI: 4.0, sky: '#cdd9e3', ground: '#9a8670', hemiI: 0.55, env: 0.2, glow: 0 },
    { alt: 45, top: '#c6d6dd', bottom: '#edece7', sun: '#fff3e4', sunI: 4.4, sky: '#dbe5eb', ground: '#a59683', hemiI: 0.62, env: 0.22, glow: 0 },
];

export function mount(stage, { reducedMotion = false } = {}) {
    const hero = stage.closest('[data-hero]');
    const canvas = stage.querySelector('canvas');
    const dial = hero.querySelector('[data-sun-dial]');
    const range = dial.querySelector('input[type="range"]');
    const clock = dial.querySelector('[data-sun-clock]');
    const altitudeLabel = dial.querySelector('[data-sun-altitude]');
    const scale = dial.querySelector('[data-sun-scale]');
    const lat = Number(stage.dataset.lat) || 11.23;
    const lon = Number(stage.dataset.lon) || 75.98;
    const small = window.matchMedia('(max-width: 760px)').matches;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, small ? 1.75 : 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();

    const camera = new THREE.PerspectiveCamera(24, 1, 1, 400);
    const target = new THREE.Vector3(0, 2.2, -0.5);

    const model = buildModel();
    scene.add(model.root);

    const sun = new THREE.DirectionalLight(0xffffff, 3);
    sun.castShadow = true;
    sun.shadow.mapSize.set(small ? 1024 : 2048, small ? 1024 : 2048);
    Object.assign(sun.shadow.camera, { left: -19, right: 19, top: 19, bottom: -19, near: 5, far: 110 });
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.035;
    sun.target.position.set(0, 0, 0);
    scene.add(sun, sun.target);

    const hemi = new THREE.HemisphereLight(0xdbe5eb, 0xa59683, 0.9);
    scene.add(hemi);

    // ----- time of day ------------------------------------------------------

    const today = istNow();
    const span = daylight(today.day, lat, lon);
    const min = Math.floor((span.sunrise - 45) / 5) * 5;
    const max = Math.ceil((span.sunset + 60) / 5) * 5;
    range.min = String(min);
    range.max = String(max);

    const requested = Number(new URLSearchParams(location.search).get('sun'));
    let startMinutes;
    if (requested >= min && requested <= max) {
        startMinutes = requested;
    } else if (today.minutes >= span.sunrise + 20 && today.minutes <= span.sunset + 45) {
        startMinutes = today.minutes;
    } else if (today.minutes > span.sunset + 45 || today.minutes < 240) {
        startMinutes = span.sunset + 30;
    } else {
        startMinutes = span.sunrise + 60;
    }
    range.value = String(Math.round(startMinutes));
    buildScale(scale, min, max);

    let minutes = startMinutes;
    const lightState = { top: new THREE.Color(), bottom: new THREE.Color() };

    const applyTime = (value) => {
        minutes = value;
        const pos = sunPosition(value, today.day, lat, lon);
        const altDeg = pos.altitude / RAD;
        const key = sampleKeys(altDeg);

        const shadowAlt = Math.max(pos.altitude, 2.5 * RAD);
        const dir = new THREE.Vector3(
            Math.cos(pos.azimuth) * Math.cos(shadowAlt),
            Math.sin(shadowAlt),
            Math.sin(pos.azimuth) * Math.cos(shadowAlt),
        );
        sun.position.copy(dir.multiplyScalar(60));
        sun.color.copy(key.sun);
        sun.intensity = key.sunI;
        hemi.color.copy(key.sky);
        hemi.groundColor.copy(key.ground);
        hemi.intensity = key.hemiI;
        scene.environmentIntensity = key.env;
        model.glass.emissiveIntensity = key.glow * 2.4;
        model.lamps.forEach((lamp) => {
            lamp.intensity = key.glow * lamp.userData.peak;
        });

        lightState.top.copy(key.top);
        lightState.bottom.copy(key.bottom);
        hero.style.setProperty('--sky-top', `#${key.top.getHexString()}`);
        hero.style.setProperty('--sky-bottom', `#${key.bottom.getHexString()}`);
        document.documentElement.dataset.heroLight = altDeg < -3 ? 'night' : 'day';

        clock.value = formatTime(value);
        if (altDeg > 0.5) {
            altitudeLabel.textContent = `Sun ${Math.round(altDeg)}° above the horizon`;
        } else {
            altitudeLabel.textContent = value < 720 ? 'Before sunrise' : 'After sunset';
        }
        range.setAttribute('aria-valuetext', `${formatTime(value)}, ${altitudeLabel.textContent}`);
    };

    // ----- camera framing ---------------------------------------------------

    const view = { azimuth: -0.66, elevation: 0.53, dragAzimuth: 0, dragTarget: 0, px: 0, py: 0, tx: 0, ty: 0, scroll: 0 };
    let width = 1;
    let height = 1;

    const resize = () => {
        const rect = stage.getBoundingClientRect();
        width = Math.max(1, Math.round(rect.width));
        height = Math.max(1, Math.round(rect.height));
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        requestRender();
    };

    const placeCamera = () => {
        const portrait = width / height < 0.9;
        const frame = portrait
            ? { fw: 1.12, fh: 0.46, cx: 0.5, cy: 0.63 }
            : { fw: 0.52, fh: 0.8, cx: 0.705, cy: 0.52 };
        const radius = 14.6;
        const tanHalf = Math.tan((camera.fov * RAD) / 2);
        const vHalf = Math.atan(tanHalf * frame.fh);
        const hHalf = Math.atan(tanHalf * camera.aspect * frame.fw);
        const distance = radius / Math.sin(Math.min(vHalf, hHalf));

        const azimuth = view.azimuth + view.dragAzimuth + view.px * 0.05;
        const elevation = view.elevation + view.py * 0.03 + view.scroll * 0.22;
        camera.position.set(
            target.x + distance * Math.cos(elevation) * Math.sin(azimuth),
            target.y + distance * Math.sin(elevation),
            target.z + distance * Math.cos(elevation) * Math.cos(azimuth),
        );
        camera.lookAt(target);
        camera.setViewOffset(width, height, -(frame.cx - 0.5) * width, -(frame.cy - 0.5) * height, width, height);
        camera.updateProjectionMatrix();
    };

    // ----- render loop ------------------------------------------------------

    const clockTimer = new THREE.Clock();
    const intro = { active: !reducedMotion, start: 0, duration: 2.8, from: startMinutes - 100 };
    let running = false;
    let visible = true;
    let lastActivity = 0;
    let elapsed = 0;
    let firstFrame = true;

    if (!intro.active) {
        model.setProgress(1);
    }

    function frame() {
        if (!running) {
            return;
        }
        const dt = Math.min(clockTimer.getDelta(), 0.05);
        elapsed += dt;
        step(dt);
        draw();
        const idle = elapsed - lastActivity > 10 && !intro.active && !dragging;
        if (reducedMotion || idle || !visible) {
            running = false;
            return;
        }
        requestAnimationFrame(frame);
    }

    function step(dt) {
        if (intro.active) {
            const t = Math.min((elapsed - intro.start) / intro.duration, 1);
            model.setProgress(t);
            const sunT = easeInOut(Math.min(t * 1.1, 1));
            applyTime(intro.from + (startMinutes - intro.from) * sunT);
            if (t >= 1) {
                intro.active = false;
                applyTime(Number(range.value));
                lastActivity = elapsed;
            }
        }
        const ease = 1 - Math.exp(-dt * 6);
        view.dragAzimuth += (view.dragTarget - view.dragAzimuth) * ease;
        view.px += (view.tx - view.px) * ease * 0.6;
        view.py += (view.ty - view.py) * ease * 0.6;
        if (!reducedMotion) {
            model.sway(elapsed);
        }
    }

    function draw() {
        placeCamera();
        renderer.render(scene, camera);
        if (firstFrame) {
            firstFrame = false;
            hero.classList.add('is-live');
            dial.hidden = false;
        }
    }

    function requestRender() {
        lastActivity = elapsed;
        if (reducedMotion) {
            if (!running) {
                running = true;
                requestAnimationFrame(() => {
                    running = false;
                    draw();
                });
            }
            return;
        }
        if (!running && visible) {
            running = true;
            clockTimer.getDelta();
            requestAnimationFrame(frame);
        }
    }

    // ----- input ------------------------------------------------------------

    range.addEventListener('input', () => {
        intro.active = false;
        model.setProgress(1);
        applyTime(Number(range.value));
        requestRender();
    });

    let dragging = false;
    let dragX = 0;
    let dragStart = 0;
    canvas.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'touch') {
            return;
        }
        dragging = true;
        dragX = event.clientX;
        dragStart = view.dragTarget;
        canvas.setPointerCapture(event.pointerId);
        hero.classList.add('is-dragging');
    });
    canvas.addEventListener('pointermove', (event) => {
        if (event.pointerType === 'touch') {
            return;
        }
        if (dragging) {
            const dx = (event.clientX - dragX) / width;
            view.dragTarget = THREE.MathUtils.clamp(dragStart + dx * 2.4, -0.75, 0.75);
        } else if (!reducedMotion) {
            view.tx = (event.clientX / width) * 2 - 1;
            view.ty = (event.clientY / height) * 2 - 1;
        }
        requestRender();
    });
    const endDrag = () => {
        dragging = false;
        hero.classList.remove('is-dragging');
        requestRender();
    };
    canvas.addEventListener('pointerup', endDrag);
    canvas.addEventListener('pointercancel', endDrag);

    if (!reducedMotion) {
        window.addEventListener('scroll', () => {
            const rect = hero.getBoundingClientRect();
            view.scroll = THREE.MathUtils.clamp(-rect.top / rect.height, 0, 1);
            requestRender();
        }, { passive: true });
    }

    new ResizeObserver(resize).observe(stage);
    new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        if (visible) {
            requestRender();
        }
    }).observe(hero);
    document.addEventListener('visibilitychange', () => {
        visible = !document.hidden;
        if (visible) {
            requestRender();
        }
    });
    canvas.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        hero.classList.remove('is-live');
        dial.hidden = true;
        running = false;
    });

    applyTime(intro.active ? intro.from : startMinutes);
    resize();
    intro.start = elapsed;
    requestRender();
}

// ----- sun position (NOAA-style approximation) ------------------------------

function istNow() {
    const now = new Date(Date.now() + 330 * 60000);
    const start = Date.UTC(now.getUTCFullYear(), 0, 0);
    const day = Math.floor((now.getTime() - start) / 86400000);
    return { day, minutes: now.getUTCHours() * 60 + now.getUTCMinutes() };
}

function solarTerms(day) {
    const declination = 23.44 * Math.sin(RAD * (360 / 365) * (284 + day)) * RAD;
    const b = RAD * (360 / 364) * (day - 81);
    const equationOfTime = 9.87 * Math.sin(2 * b) - 7.53 * Math.cos(b) - 1.5 * Math.sin(b);
    return { declination, equationOfTime };
}

function sunPosition(minutes, day, lat, lon) {
    const { declination, equationOfTime } = solarTerms(day);
    const solarMinutes = minutes + 4 * (lon - IST_MERIDIAN) + equationOfTime;
    const hourAngle = RAD * (solarMinutes / 60 - 12) * 15;
    const phi = lat * RAD;
    const altitude = Math.asin(
        Math.sin(phi) * Math.sin(declination) + Math.cos(phi) * Math.cos(declination) * Math.cos(hourAngle),
    );
    let azimuth = Math.atan2(
        -Math.sin(hourAngle),
        Math.tan(declination) * Math.cos(phi) - Math.sin(phi) * Math.cos(hourAngle),
    );
    if (azimuth < 0) {
        azimuth += Math.PI * 2;
    }
    return { altitude, azimuth };
}

function daylight(day, lat, lon) {
    const { declination, equationOfTime } = solarTerms(day);
    const phi = lat * RAD;
    const cosH = (Math.sin(-0.833 * RAD) - Math.sin(phi) * Math.sin(declination)) / (Math.cos(phi) * Math.cos(declination));
    const halfDay = (Math.acos(THREE.MathUtils.clamp(cosH, -1, 1)) / RAD) * 4;
    const noon = 720 - 4 * (lon - IST_MERIDIAN) - equationOfTime;
    return { sunrise: noon - halfDay, sunset: noon + halfDay };
}

function sampleKeys(alt) {
    const keys = LIGHT_KEYS;
    let i = 0;
    while (i < keys.length - 2 && alt > keys[i + 1].alt) {
        i += 1;
    }
    const a = keys[i];
    const b = keys[i + 1];
    const t = THREE.MathUtils.clamp((alt - a.alt) / (b.alt - a.alt), 0, 1);
    const mix = (x, y) => new THREE.Color(x).lerp(new THREE.Color(y), t);
    const num = (x, y) => x + (y - x) * t;
    return {
        top: mix(a.top, b.top),
        bottom: mix(a.bottom, b.bottom),
        sun: mix(a.sun, b.sun),
        sky: mix(a.sky, b.sky),
        ground: mix(a.ground, b.ground),
        sunI: num(a.sunI, b.sunI),
        hemiI: num(a.hemiI, b.hemiI),
        env: num(a.env, b.env),
        glow: num(a.glow, b.glow),
    };
}

function formatTime(value) {
    let hours = Math.floor(value / 60);
    let mins = Math.round(value - hours * 60);
    if (mins === 60) {
        hours += 1;
        mins = 0;
    }
    const suffix = hours >= 12 && hours < 24 ? 'pm' : 'am';
    const h12 = ((hours + 11) % 12) + 1;
    return `${h12}:${String(mins).padStart(2, '0')} ${suffix}`;
}

function buildScale(container, min, max) {
    const labels = { 6: '6 am', 9: '9 am', 12: 'Noon', 15: '3 pm', 18: '6 pm' };
    const ticks = [];
    for (let hour = Math.ceil(min / 60); hour * 60 <= max; hour += 1) {
        const left = ((hour * 60 - min) / (max - min)) * 100;
        const label = labels[hour];
        ticks.push(
            `<span class="sun-dial__tick${label ? ' sun-dial__tick--major' : ''}" style="left:${left.toFixed(2)}%">${label ? `<span>${label}</span>` : ''}</span>`,
        );
    }
    container.innerHTML = ticks.join('');
}

function easeOut(t) {
    return 1 - Math.pow(1 - t, 3);
}

function easeInOut(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// ----- model ----------------------------------------------------------------

function buildModel() {
    const root = new THREE.Group();
    const textures = makeTextures();

    const mat = {
        board: new THREE.MeshStandardMaterial({ color: '#e8e5de', roughness: 0.95 }),
        boardEdge: new THREE.MeshStandardMaterial({ color: '#cfc9bd', roughness: 0.95 }),
        lawn: new THREE.MeshStandardMaterial({ color: '#97a283', roughness: 1, map: textures.grass }),
        paver: new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.9, map: textures.paver }),
        stone: new THREE.MeshStandardMaterial({ color: '#b9b3a7', roughness: 0.85 }),
        laterite: new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 1, map: textures.laterite }),
        plaster: new THREE.MeshStandardMaterial({ color: '#efece5', roughness: 0.92 }),
        slab: new THREE.MeshStandardMaterial({ color: '#dcd8cf', roughness: 0.9 }),
        timber: new THREE.MeshStandardMaterial({ color: '#6b4429', roughness: 0.65 }),
        roof: new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.78, map: textures.tiles, bumpMap: textures.tilesBump, bumpScale: 2.2, side: THREE.DoubleSide }),
        ridge: new THREE.MeshStandardMaterial({ color: '#8c3d22', roughness: 0.8 }),
        glass: new THREE.MeshStandardMaterial({ color: '#24302f', roughness: 0.12, metalness: 0.1, emissive: '#ffbd72', emissiveIntensity: 0, envMapIntensity: 1.4 }),
        jaali: new THREE.MeshStandardMaterial({ color: '#b66a43', roughness: 0.95, alphaMap: textures.jaali, alphaTest: 0.5, side: THREE.DoubleSide }),
        water: new THREE.MeshStandardMaterial({ color: '#5d8e98', roughness: 0.06, metalness: 0.05, envMapIntensity: 1.6 }),
        oxide: new THREE.MeshStandardMaterial({ color: '#8c2f22', roughness: 0.32, envMapIntensity: 1.2 }),
        trunk: new THREE.MeshStandardMaterial({ color: '#8b7b67', roughness: 0.95 }),
        frond: new THREE.MeshStandardMaterial({ color: '#5d7a49', roughness: 0.85, alphaMap: textures.frond, alphaTest: 0.42, side: THREE.DoubleSide }),
        canopy: new THREE.MeshStandardMaterial({ color: '#6d8a57', roughness: 0.95, flatShading: true }),
        shrub: new THREE.MeshStandardMaterial({ color: '#7d965f', roughness: 0.95, flatShading: true }),
    };
    mat.roof.shadowSide = THREE.DoubleSide;
    mat.frond.shadowSide = THREE.DoubleSide;
    mat.jaali.shadowSide = THREE.DoubleSide;

    // Stages assemble in order during the intro.
    const stages = ['ground', 'base', 'walls', 'upper', 'roofs'].map((name) => {
        const group = new THREE.Group();
        group.name = name;
        root.add(group);
        return group;
    });
    const [groundStage, baseStage, wallStage, upperStage, roofStage] = stages;
    const buckets = new Map();
    const add = (stageGroup, geometry, material, { cast = true, receive = true } = {}) => {
        const key = `${stageGroup.name}|${material.uuid}|${cast}|${receive}`;
        if (!buckets.has(key)) {
            buckets.set(key, { stageGroup, material, cast, receive, geometries: [] });
        }
        buckets.get(key).geometries.push(geometry.index ? geometry.toNonIndexed() : geometry);
    };

    // Site board, lawn, paving.
    const board = new THREE.BoxGeometry(30, 0.6, 22);
    board.translate(0, -0.3, 0);
    const boardMesh = new THREE.Mesh(board, [mat.boardEdge, mat.boardEdge, mat.board, mat.boardEdge, mat.boardEdge, mat.boardEdge]);
    boardMesh.receiveShadow = true;
    groundStage.add(boardMesh);
    root.add(contactShadow());

    add(groundStage, box(-14.2, 14.2, 0, 0.03, -10.2, 10.2), mat.lawn, { cast: false });
    add(groundStage, box(2.6, 7.9, 0.03, 0.06, 4.5, 10.6), mat.paver, { cast: false });
    [[5.15, 0.9], [6.0, 0.6], [6.9, -0.2], [7.8, -1.2]].forEach(([z, x]) => {
        add(groundStage, box(x - 0.45, x + 0.45, 0.03, 0.07, z - 0.35, z + 0.35), mat.stone, { cast: false });
    });

    // Pool on the south lawn.
    [
        [-13.4, -8.4, -3.3, -2.8],
        [-13.4, -8.4, 1.0, 1.5],
        [-13.4, -12.9, -2.8, 1.0],
        [-8.9, -8.4, -2.8, 1.0],
    ].forEach(([x0, x1, z0, z1]) => add(groundStage, box(x0, x1, 0.03, 0.22, z0, z1), mat.stone));
    add(groundStage, box(-12.9, -8.9, 0.03, 0.15, -2.8, 1.0), mat.water, { cast: false });

    // Compound wall with a gate opening at the front.
    const wallH = 0.95;
    const wallRuns = [
        [-14.6, 14.6, -10.6, -10.36],
        [-14.6, -14.36, -10.6, 10.6],
        [14.36, 14.6, -10.6, 10.6],
        [-14.6, 2.3, 10.36, 10.6],
        [8.2, 14.6, 10.36, 10.6],
    ];
    wallRuns.forEach(([x0, x1, z0, z1]) => {
        add(baseStage, box(x0, x1, 0, wallH, z0, z1), mat.laterite);
        add(baseStage, box(x0 - 0.04, x1 + 0.04, wallH, wallH + 0.08, z0 - 0.04, z1 + 0.04), mat.plaster);
    });
    [2.0, 8.5].forEach((x) => {
        add(baseStage, box(x - 0.32, x + 0.32, 0, 1.6, 10.16, 10.8), mat.laterite);
        add(baseStage, box(x - 0.38, x + 0.38, 1.6, 1.72, 10.1, 10.86), mat.plaster);
    });

    // Plinth and steps.
    const PL = 0.45;
    add(baseStage, box(-7.3, 7.3, 0, PL, -6.6, 4.6), mat.laterite);
    add(baseStage, box(-1.2, 1.2, 0, 0.3, 4.6, 5.0), mat.stone);
    add(baseStage, box(-1.2, 1.2, 0, 0.15, 5.0, 5.4), mat.stone);

    // Ground floor: south wing, north wing, back block around a courtyard.
    const G0 = PL;
    const G1 = PL + 3.1;
    add(wallStage, box(-7.0, -2.4, G0, G1, -6.3, 3.0), mat.plaster);
    add(wallStage, box(2.4, 7.0, G0, G1, -6.3, 1.2), mat.plaster);
    add(wallStage, box(-2.4, 2.4, G0, G1, -6.3, -3.2), mat.plaster);
    add(wallStage, box(-2.4, 2.4, G0, G1, 0.45, 0.7), mat.plaster);
    add(wallStage, box(-2.4, 2.4, PL, PL + 0.02, -3.2, 0.45), mat.stone, { cast: false });
    add(wallStage, box(-2.4, 2.4, PL, PL + 0.015, 0.7, 4.45), mat.oxide, { cast: false });

    // Openings: glass panes proud of the wall faces, timber door.
    const glassPanes = [
        box(-6.4, -3.2, G0 + 0.9, G1 - 0.35, 3.0, 3.04),
        box(-7.04, -7.0, G0 + 0.9, G1 - 0.35, -4.8, -2.6),
        box(-7.04, -7.0, G0 + 0.9, G1 - 0.35, -1.0, 1.6),
        box(3.0, 6.4, G0 + 0.2, G1 - 0.35, 1.2, 1.24),
        box(-2.0, -1.0, G0 + 0.9, G1 - 0.5, 0.7, 0.74),
        box(1.0, 2.0, G0 + 0.9, G1 - 0.5, 0.7, 0.74),
        box(7.0, 7.04, G0 + 0.9, G1 - 0.35, -5.0, -1.6),
    ];
    glassPanes.forEach((g) => add(wallStage, g, mat.glass, { cast: false }));
    add(wallStage, box(-0.6, 0.6, G0, G1 - 0.45, 0.7, 0.76), mat.timber, { cast: false });
    [-6.4, -3.2].forEach((x) => add(wallStage, box(x - 0.06, x + 0.06, G0 + 0.9, G1 - 0.35, 3.0, 3.08), mat.timber, { cast: false }));

    // Courtyard columns and a small tree.
    [[-1.7, -2.5], [1.7, -2.5], [-1.7, -0.1], [1.7, -0.1]].forEach(([x, z]) => {
        add(wallStage, cylinder(0.11, x, z, 0.25, 2.85), mat.timber);
    });

    // Verandah (poomukham): columns and charupadi benches.
    const V1 = 3.2;
    [-2.15, -0.85, 0.85, 2.15].forEach((x) => {
        add(wallStage, box(x - 0.17, x + 0.17, G0, G0 + 0.12, 4.0, 4.34), mat.stone);
        add(wallStage, cylinder(0.12, x, 4.17, G0 + 0.12, V1), mat.timber);
    });
    [[-2.15, -0.85], [0.85, 2.15]].forEach(([a, b]) => {
        add(wallStage, box(a + 0.14, b - 0.14, G0, G0 + 0.45, 3.75, 4.3), mat.timber);
        add(wallStage, tilted(a + 0.14, b - 0.14, G0 + 0.45, G0 + 1.05, 4.24, 4.42, 0.06), mat.timber);
    });

    // North porch: a thin cantilevered slab on one column.
    add(upperStage, box(2.2, 8.4, G1 - 0.3, G1, 1.2, 6.2), mat.slab);
    add(wallStage, cylinder(0.12, 8.0, 5.8, G0, G1 - 0.3), mat.plaster);

    // North wing roof terrace with parapet and a timber pergola.
    const T = G1 + 0.25;
    add(upperStage, box(2.3, 7.1, G1, T, -6.4, 1.3), mat.slab);
    [
        [2.3, 7.1, -6.4, -6.22],
        [2.3, 7.1, 1.12, 1.3],
        [6.92, 7.1, -6.4, 1.3],
    ].forEach(([x0, x1, z0, z1]) => add(upperStage, box(x0, x1, T, T + 0.95, z0, z1), mat.plaster));
    const P0 = T + 2.5;
    [[3.0, -3.0], [6.5, -3.0], [3.0, 0.7], [6.5, 0.7]].forEach(([x, z]) => {
        add(upperStage, box(x - 0.09, x + 0.09, T, P0, z - 0.09, z + 0.09), mat.timber);
    });
    [-3.0, 0.7].forEach((z) => add(upperStage, box(2.8, 6.7, P0, P0 + 0.2, z - 0.08, z + 0.08), mat.timber));
    for (let x = 2.9; x <= 6.65; x += 0.34) {
        add(upperStage, box(x - 0.04, x + 0.04, P0 + 0.2, P0 + 0.38, -3.3, 1.0), mat.timber);
    }

    // Upper floor on the south wing with a screened (jaali) front.
    const U0 = G1;
    const U1 = G1 + 3.0;
    add(upperStage, box(-6.8, -2.6, U0, U1, -6.1, 2.2), mat.plaster);
    add(upperStage, box(-6.84, -6.8, U0 + 0.7, U1 - 0.4, -4.6, -1.4), mat.glass, { cast: false });
    add(upperStage, box(-6.84, -6.8, U0 + 0.7, U1 - 0.4, -0.4, 1.5), mat.glass, { cast: false });
    add(upperStage, box(-6.2, -3.2, U0 + 0.15, U1 - 0.4, 2.2, 2.24), mat.glass, { cast: false });
    add(upperStage, box(-6.6, -2.8, U0, U0 + 0.14, 2.2, 3.1), mat.slab);
    const jaali = new THREE.PlaneGeometry(3.8, 2.75);
    jaali.translate(-4.7, U0 + 0.14 + 1.375, 3.02);
    add(upperStage, jaali, mat.jaali);

    // Roofs: big hip roof, verandah hip roof, courtyard ring, ridge caps.
    const mainRoof = hipRoof(-6.8, -2.6, -6.1, 2.2, U1, 30, 1.15);
    add(roofStage, mainRoof.geometry, mat.roof);
    add(roofStage, mainRoof.ridge(0.16), mat.ridge);
    mainRoof.fascia(0.22, 0.07).forEach((g) => add(roofStage, g, mat.timber));

    const verandahRoof = hipRoof(-2.55, 2.55, 0.9, 4.25, V1, 30, 0.75);
    add(roofStage, verandahRoof.geometry, mat.roof);
    add(roofStage, verandahRoof.ridge(0.14), mat.ridge);
    verandahRoof.fascia(0.18, 0.06).forEach((g) => add(roofStage, g, mat.timber));

    add(roofStage, ringRoof([-3.2, 3.2, -4.0, 1.0, G1 + 0.3], [-1.85, 1.85, -2.65, 0.05, 2.85]), mat.roof);

    // Merge each stage/material bucket into one mesh.
    buckets.forEach(({ stageGroup, material, cast, receive, geometries }) => {
        const mesh = new THREE.Mesh(mergeGeometries(geometries), material);
        mesh.castShadow = cast;
        mesh.receiveShadow = receive;
        stageGroup.add(mesh);
    });

    // Landscape grows in last; each item scales from its own base.
    const growers = [];
    const palms = [];
    const palmSpecs = [
        [-11.2, 7.6, 10.4, 0.8, -0.4, 1],
        [-12.6, -6.4, 11.6, 0.4, 0.7, 2],
        [11.4, -7.8, 9.6, -0.7, 0.3, 3],
        [12.1, 7.2, 10.8, -0.5, -0.6, 4],
        [-9.4, -9.2, 8.8, 0.6, 0.5, 5],
    ];
    palmSpecs.forEach(([x, z, h, lx, lz, seed]) => {
        const palm = makePalm(h, lx, lz, seed, mat);
        palm.position.set(x, 0, z);
        root.add(palm);
        growers.push(palm);
        palms.push(palm.userData.crown);
    });
    [[9.6, -1.6, 2.2, 6], [-10.4, 2.4, 1.6, 7], [0, -1.3, 0.85, 8]].forEach(([x, z, r, seed]) => {
        const tree = makeTree(r, seed, mat);
        tree.position.set(x, z === -1.3 ? 0.47 : 0, z);
        root.add(tree);
        growers.push(tree);
    });
    const shrubRandom = random(11);
    for (let x = -13.6; x < 1.6; x += 1.15) {
        const shrub = makeShrub(0.38 + shrubRandom() * 0.3, mat);
        shrub.position.set(x + shrubRandom() * 0.3, 0, 9.65 - shrubRandom() * 0.3);
        root.add(shrub);
        growers.push(shrub);
    }
    [[-6.6, 4.1], [-5.4, 4.0], [-4.2, 4.2], [4.0, 7.0], [3.2, 9.0], [-13.6, -9.6], [-13.4, 9.4], [13.6, 9.6], [13.6, 0.5], [13.7, -3.0]].forEach(([x, z]) => {
        const shrub = makeShrub(0.45 + shrubRandom() * 0.35, mat);
        shrub.position.set(x, 0, z);
        root.add(shrub);
        growers.push(shrub);
    });

    // Night lights under the verandah, porch and courtyard.
    const lamps = [
        [0, 2.9, 2.6, 9],
        [5.2, G1 - 0.45, 3.6, 7],
        [0, 2.6, -1.3, 5],
        [-4.7, U0 + 2.2, 2.6, 4],
    ].map(([x, y, z, peak]) => {
        const lamp = new THREE.PointLight('#ffb867', 0, 9, 2);
        lamp.position.set(x, y, z);
        lamp.userData.peak = peak;
        root.add(lamp);
        return lamp;
    });

    const setProgress = (t) => {
        const phase = (start, duration = 0.32) => easeOut(THREE.MathUtils.clamp((t - start) / duration, 0, 1));
        baseStage.scale.y = Math.max(phase(0.02), 0.001);
        wallStage.scale.y = Math.max(phase(0.16), 0.001);
        upperStage.scale.y = Math.max(phase(0.3), 0.001);
        const roofIn = phase(0.44, 0.3);
        roofStage.visible = roofIn > 0;
        roofStage.position.y = (1 - roofIn) * 4.5;
        growers.forEach((item, index) => {
            const s = phase(0.5 + (index % 9) * 0.035, 0.36);
            item.scale.setScalar(Math.max(s, 0.001));
            item.visible = s > 0;
        });
    };

    const sway = (time) => {
        palms.forEach((crown, i) => {
            crown.rotation.z = Math.sin(time * 0.9 + i * 1.7) * 0.025;
            crown.rotation.x = Math.cos(time * 0.7 + i * 2.3) * 0.018;
        });
    };

    return { root, glass: mat.glass, lamps, setProgress, sway };
}

// ----- geometry helpers -----------------------------------------------------

function worldUV(geometry) {
    const pos = geometry.attributes.position;
    const nor = geometry.attributes.normal;
    const uv = new Float32Array(pos.count * 2);
    for (let i = 0; i < pos.count; i += 1) {
        const nx = Math.abs(nor.getX(i));
        const ny = Math.abs(nor.getY(i));
        const nz = Math.abs(nor.getZ(i));
        let u;
        let v;
        if (ny >= nx && ny >= nz) {
            u = pos.getX(i);
            v = pos.getZ(i);
        } else if (nx >= nz) {
            u = pos.getZ(i);
            v = pos.getY(i);
        } else {
            u = pos.getX(i);
            v = pos.getY(i);
        }
        uv[i * 2] = u;
        uv[i * 2 + 1] = v;
    }
    geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    return geometry;
}

function box(x0, x1, y0, y1, z0, z1) {
    const geometry = new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0);
    geometry.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    return worldUV(geometry);
}

function cylinder(radius, x, z, y0, y1) {
    const geometry = new THREE.CylinderGeometry(radius, radius, y1 - y0, 10);
    geometry.translate(x, (y0 + y1) / 2, z);
    return worldUV(geometry);
}

function tilted(x0, x1, y0, y1, z0, z1, thickness) {
    // A backrest slab leaning outward from (y0, z0) to (y1, z1).
    const length = Math.hypot(y1 - y0, z1 - z0);
    const geometry = new THREE.BoxGeometry(x1 - x0, length, thickness);
    geometry.rotateX(-Math.atan2(z1 - z0, y1 - y0));
    geometry.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    return worldUV(geometry);
}

function faceGeometry(faces) {
    // faces: arrays of THREE.Vector3 (3 or 4 points, counter-clockwise from outside).
    // UVs run along the first edge (the eave) and up the slope, in metres.
    const positions = [];
    const normals = [];
    const uvs = [];
    faces.forEach((points) => {
        const [a, b, c] = points;
        const normal = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a)).normalize();
        if (normal.y < 0) {
            points.reverse();
            normal.negate();
        }
        const eave = new THREE.Vector3().subVectors(points[1], points[0]).normalize();
        const up = new THREE.Vector3().crossVectors(normal, eave).normalize();
        const origin = points[0];
        const project = (p) => {
            const d = new THREE.Vector3().subVectors(p, origin);
            return [d.dot(eave), d.dot(up)];
        };
        const tris = points.length === 4 ? [[0, 1, 2], [0, 2, 3]] : [[0, 1, 2]];
        tris.forEach((tri) => {
            tri.forEach((index) => {
                const p = points[index];
                positions.push(p.x, p.y, p.z);
                normals.push(normal.x, normal.y, normal.z);
                uvs.push(...project(p));
            });
        });
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    return geometry;
}

function hipRoof(x0, x1, z0, z1, y, pitchDeg, overhang) {
    const ex0 = x0 - overhang;
    const ex1 = x1 + overhang;
    const ez0 = z0 - overhang;
    const ez1 = z1 + overhang;
    const w = ex1 - ex0;
    const d = ez1 - ez0;
    const half = Math.min(w, d) / 2;
    const h = half * Math.tan(pitchDeg * RAD);
    const v = (px, py, pz) => new THREE.Vector3(px, py, pz);
    const A = v(ex0, y, ez1);
    const B = v(ex1, y, ez1);
    const C = v(ex1, y, ez0);
    const D = v(ex0, y, ez0);
    let r0;
    let r1;
    let faces;
    if (w >= d) {
        r0 = v(ex0 + half, y + h, (ez0 + ez1) / 2);
        r1 = v(ex1 - half, y + h, (ez0 + ez1) / 2);
        faces = [[A, B, r1, r0], [B, C, r1], [C, D, r0, r1], [D, A, r0]];
    } else {
        r0 = v((ex0 + ex1) / 2, y + h, ez0 + half);
        r1 = v((ex0 + ex1) / 2, y + h, ez1 - half);
        faces = [[A, B, r1], [B, C, r0, r1], [C, D, r0], [D, A, r1, r0]];
    }
    const geometry = faceGeometry(faces.map((f) => f.map((p) => p.clone())));
    return {
        geometry,
        ridge(size) {
            const length = r0.distanceTo(r1) + size;
            const g = new THREE.BoxGeometry(w >= d ? length : size, size * 0.7, w >= d ? size : length);
            g.translate((r0.x + r1.x) / 2, y + h + size * 0.15, (r0.z + r1.z) / 2);
            return worldUV(g);
        },
        fascia(depth, thickness) {
            return [
                box(ex0, ex1, y - depth, y, ez1 - thickness, ez1),
                box(ex0, ex1, y - depth, y, ez0, ez0 + thickness),
                box(ex0, ex0 + thickness, y - depth, y, ez0, ez1),
                box(ex1 - thickness, ex1, y - depth, y, ez0, ez1),
            ];
        },
    };
}

function ringRoof([ox0, ox1, oz0, oz1, oy], [ix0, ix1, iz0, iz1, iy]) {
    // Four slopes draining inward to an open courtyard (nadumuttam).
    const v = (x, y, z) => new THREE.Vector3(x, y, z);
    const O = [v(ox0, oy, oz1), v(ox1, oy, oz1), v(ox1, oy, oz0), v(ox0, oy, oz0)];
    const I = [v(ix0, iy, iz1), v(ix1, iy, iz1), v(ix1, iy, iz0), v(ix0, iy, iz0)];
    const faces = [];
    for (let i = 0; i < 4; i += 1) {
        const j = (i + 1) % 4;
        faces.push([I[i].clone(), I[j].clone(), O[j].clone(), O[i].clone()]);
    }
    return faceGeometry(faces);
}

function contactShadow() {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createRadialGradient(size / 2, size / 2, size * 0.18, size / 2, size / 2, size / 2);
    gradient.addColorStop(0, 'rgba(20, 24, 22, 0.55)');
    gradient.addColorStop(1, 'rgba(20, 24, 22, 0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const plane = new THREE.Mesh(
        new THREE.PlaneGeometry(44, 34),
        new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false }),
    );
    plane.rotation.x = -Math.PI / 2;
    plane.position.y = -0.62;
    plane.renderOrder = -1;
    return plane;
}

// ----- planting -------------------------------------------------------------

function random(seed) {
    let s = seed * 9301 + 49297;
    return () => {
        s = (s * 9301 + 49297) % 233280;
        return s / 233280;
    };
}

function makePalm(height, leanX, leanZ, seed, mat) {
    const rand = random(seed);
    const group = new THREE.Group();

    const trunk = new THREE.CylinderGeometry(0.12, 0.2, height, 8, 16, true);
    trunk.translate(0, height / 2, 0);
    const pos = trunk.attributes.position;
    for (let i = 0; i < pos.count; i += 1) {
        const t = pos.getY(i) / height;
        pos.setX(i, pos.getX(i) + leanX * t * t);
        pos.setZ(i, pos.getZ(i) + leanZ * t * t);
    }
    trunk.computeVertexNormals();
    const trunkMesh = new THREE.Mesh(trunk, mat.trunk);
    trunkMesh.castShadow = true;
    trunkMesh.receiveShadow = true;
    group.add(trunkMesh);

    const crown = new THREE.Group();
    crown.position.set(leanX, height, leanZ);
    const fronds = [];
    const count = 14;
    for (let i = 0; i < count; i += 1) {
        const angle = (i / count) * Math.PI * 2 + rand() * 0.4;
        const length = 3.3 + rand() * 1.1;
        const lift = 0.25 + rand() * 0.45;
        const droop = 0.75 + rand() * 0.55;
        fronds.push(frondGeometry(length, lift, droop, angle));
    }
    const frondMesh = new THREE.Mesh(mergeGeometries(fronds), mat.frond);
    frondMesh.castShadow = true;
    frondMesh.receiveShadow = true;
    crown.add(frondMesh);
    group.add(crown);
    group.userData.crown = crown;
    return group;
}

function frondGeometry(length, lift, droop, angle) {
    const segments = 12;
    const positions = [];
    const uvs = [];
    const indices = [];
    const dir = new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
    const side = new THREE.Vector3(-dir.z, 0, dir.x);
    for (let s = 0; s <= segments; s += 1) {
        const t = s / segments;
        const reach = length * t;
        const y = length * (lift * t - droop * t * t);
        const halfWidth = 0.62 * Math.pow(Math.sin(Math.PI * Math.min(t * 1.05, 1)), 0.6) + 0.02;
        const center = dir.clone().multiplyScalar(reach).setY(y);
        const fold = halfWidth * 0.32;
        [-1, 0, 1].forEach((k, column) => {
            const p = center.clone().addScaledVector(side, k * halfWidth);
            p.y -= Math.abs(k) * fold;
            positions.push(p.x, p.y, p.z);
            uvs.push(column / 2, t);
        });
    }
    for (let s = 0; s < segments; s += 1) {
        for (let c = 0; c < 2; c += 1) {
            const a = s * 3 + c;
            const b = a + 1;
            const d = a + 3;
            const e = d + 1;
            indices.push(a, d, b, b, d, e);
        }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry.toNonIndexed();
}

function makeTree(radius, seed, mat) {
    const rand = random(seed);
    const group = new THREE.Group();
    const trunkHeight = radius * 1.5;
    const trunk = new THREE.CylinderGeometry(radius * 0.08, radius * 0.12, trunkHeight, 7);
    trunk.translate(0, trunkHeight / 2, 0);
    const parts = [];
    for (let i = 0; i < 5; i += 1) {
        const r = radius * (0.55 + rand() * 0.35);
        const blob = new THREE.IcosahedronGeometry(r, 1);
        blob.translate((rand() - 0.5) * radius, trunkHeight + radius * 0.6 + (rand() - 0.3) * radius * 0.7, (rand() - 0.5) * radius);
        parts.push(blob);
    }
    const trunkMesh = new THREE.Mesh(trunk, mat.trunk);
    const canopy = new THREE.Mesh(mergeGeometries(parts), mat.canopy);
    [trunkMesh, canopy].forEach((mesh) => {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        group.add(mesh);
    });
    return group;
}

function makeShrub(radius, mat) {
    const geometry = new THREE.IcosahedronGeometry(radius, 1);
    geometry.scale(1, 0.8, 1);
    geometry.translate(0, radius * 0.7, 0);
    const mesh = new THREE.Mesh(geometry, mat.shrub);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    const group = new THREE.Group();
    group.add(mesh);
    return group;
}

// ----- textures (drawn on canvas, tiled in metres) --------------------------

function makeTextures() {
    const canvasTexture = (size, draw, { color = true, repeat = 1 } = {}) => {
        const canvas = document.createElement('canvas');
        canvas.width = size[0];
        canvas.height = size[1];
        draw(canvas.getContext('2d'), size[0], size[1]);
        const texture = new THREE.CanvasTexture(canvas);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        texture.repeat.set(repeat, repeat);
        texture.anisotropy = 4;
        if (color) {
            texture.colorSpace = THREE.SRGBColorSpace;
        }
        return texture;
    };
    const noise = (ctx, w, h, count, alpha, light) => {
        const rand = random(count);
        for (let i = 0; i < count; i += 1) {
            ctx.fillStyle = light ? `rgba(255,255,255,${alpha * rand()})` : `rgba(0,0,0,${alpha * rand()})`;
            ctx.fillRect(rand() * w, rand() * h, 1 + rand() * 2, 1 + rand() * 2);
        }
    };

    // Mangalore-style tiles: one canvas repeat = 1.2 m along the eave, 1.2 m up the slope.
    const drawTiles = (bump) => (ctx, w, h) => {
        const rows = 4;
        const cols = 5;
        const rowH = h / rows;
        const colW = w / cols;
        ctx.fillStyle = bump ? '#808080' : '#b4542f';
        ctx.fillRect(0, 0, w, h);
        for (let r = 0; r < rows; r += 1) {
            for (let c = 0; c < cols; c += 1) {
                const x = c * colW + (r % 2 ? colW / 2 : 0);
                const y = r * rowH;
                const g = ctx.createLinearGradient(x, 0, x + colW, 0);
                if (bump) {
                    g.addColorStop(0, '#5a5a5a');
                    g.addColorStop(0.5, '#e0e0e0');
                    g.addColorStop(1, '#5a5a5a');
                } else {
                    const tone = 0.9 + ((r * 7 + c * 3) % 5) * 0.04;
                    g.addColorStop(0, `rgb(${150 * tone},${62 * tone},${36 * tone})`);
                    g.addColorStop(0.5, `rgb(${196 * tone},${96 * tone},${58 * tone})`);
                    g.addColorStop(1, `rgb(${150 * tone},${62 * tone},${36 * tone})`);
                }
                ctx.fillStyle = g;
                ctx.fillRect(x, y, colW, rowH);
                ctx.fillRect(x - w, y, colW, rowH);
            }
            ctx.fillStyle = bump ? '#202020' : 'rgba(60, 22, 10, 0.55)';
            ctx.fillRect(0, r * rowH, w, rowH * 0.1);
        }
        if (!bump) {
            noise(ctx, w, h, 900, 0.12, false);
        }
    };
    const tiles = canvasTexture([256, 256], drawTiles(false));
    const tilesBump = canvasTexture([256, 256], drawTiles(true), { color: false });
    [tiles, tilesBump].forEach((t) => t.repeat.set(1 / 1.2, 1 / 1.2));

    // Laterite blocks, 0.6 x 0.3 m with pale mortar.
    const laterite = canvasTexture([256, 256], (ctx, w, h) => {
        ctx.fillStyle = '#d9cbb8';
        ctx.fillRect(0, 0, w, h);
        const rows = 8;
        const cols = 4;
        for (let r = 0; r < rows; r += 1) {
            for (let c = -1; c < cols; c += 1) {
                const x = c * (w / cols) + (r % 2 ? w / cols / 2 : 0);
                const tone = 0.88 + ((r * 5 + c * 7 + 20) % 6) * 0.03;
                ctx.fillStyle = `rgb(${172 * tone},${108 * tone},${70 * tone})`;
                ctx.fillRect(x + 2, r * (h / rows) + 2, w / cols - 4, h / rows - 4);
            }
        }
        noise(ctx, w, h, 4200, 0.45, false);
    });
    laterite.repeat.set(1 / 2.4, 1 / 2.4);

    const paver = canvasTexture([256, 256], (ctx, w, h) => {
        ctx.fillStyle = '#a7a196';
        ctx.fillRect(0, 0, w, h);
        const size = w / 8;
        for (let r = 0; r < 8; r += 1) {
            for (let c = 0; c < 8; c += 1) {
                const tone = 0.92 + ((r * 3 + c * 5) % 4) * 0.03;
                ctx.fillStyle = `rgb(${206 * tone},${200 * tone},${188 * tone})`;
                ctx.fillRect(c * size + 1.5, r * size + 1.5, size - 3, size - 3);
            }
        }
        noise(ctx, w, h, 1200, 0.12, false);
    });
    paver.repeat.set(1 / 2, 1 / 2);

    const grass = canvasTexture([256, 256], (ctx, w, h) => {
        ctx.fillStyle = '#c9cdbd';
        ctx.fillRect(0, 0, w, h);
        noise(ctx, w, h, 5000, 0.18, false);
        noise(ctx, w, h, 2500, 0.25, true);
    });
    grass.repeat.set(1 / 3, 1 / 3);

    // Jaali: a perforated screen of square openings in a diagonal lattice.
    const jaali = canvasTexture([256, 256], (ctx, w, h) => {
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = '#000000';
        const step = w / 8;
        for (let r = 0; r < 8; r += 1) {
            for (let c = 0; c < 8; c += 1) {
                ctx.save();
                ctx.translate(c * step + step / 2, r * step + step / 2);
                ctx.rotate(Math.PI / 4);
                ctx.fillRect(-step * 0.26, -step * 0.26, step * 0.52, step * 0.52);
                ctx.restore();
            }
        }
    }, { color: false });
    jaali.repeat.set(3, 2.2);

    // Coconut frond: a central rib with leaflets angled toward the tip.
    const frond = canvasTexture([128, 512], (ctx, w, h) => {
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, w, h);
        ctx.strokeStyle = '#ffffff';
        ctx.lineCap = 'round';
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(w / 2, 0);
        ctx.lineTo(w / 2, h);
        ctx.stroke();
        ctx.lineWidth = 4.6;
        for (let y = 8; y < h - 6; y += 7) {
            [-1, 1].forEach((sideSign) => {
                ctx.beginPath();
                ctx.moveTo(w / 2, y);
                ctx.lineTo(w / 2 + sideSign * (w / 2 - 3), y + 26);
                ctx.stroke();
            });
        }
    }, { color: false });
    frond.wrapS = THREE.ClampToEdgeWrapping;
    frond.wrapT = THREE.ClampToEdgeWrapping;

    return { tiles, tilesBump, laterite, paver, grass, jaali, frond };
}
