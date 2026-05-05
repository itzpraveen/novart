document.addEventListener('DOMContentLoaded', () => {
    setupWebsiteImageUploads();
    setupMediaLinkPreviews();
});

function setupMediaLinkPreviews() {
    const inputs = [...document.querySelectorAll('[data-media-link-input]')];
    inputs.forEach((input) => {
        const preview = document.querySelector(`[data-media-link-preview="${input.id}"]`);
        if (!preview) {
            return;
        }

        const render = () => {
            renderMediaLinkPreview(input, preview);
        };
        input.addEventListener('input', render);
        input.addEventListener('blur', render);
        render();
    });
}

function renderMediaLinkPreview(input, preview) {
    const platform = input.dataset.mediaLinkInput;
    const result = getMediaLinkStatus(input.value, platform);
    preview.classList.remove('is-empty', 'is-valid', 'is-invalid');
    preview.classList.add(result.state);
    preview.textContent = '';

    const message = document.createElement('span');
    message.textContent = result.message;
    preview.appendChild(message);

    if (result.href) {
        const link = document.createElement('a');
        link.href = result.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Open link';
        preview.appendChild(link);
    }
}

function getMediaLinkStatus(rawValue, platform) {
    const value = (rawValue || '').trim();
    const platformLabel = platform === 'instagram' ? 'Instagram' : 'YouTube';
    const allowedHosts = platform === 'instagram'
        ? ['instagram.com', 'www.instagram.com', 'm.instagram.com']
        : ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be'];

    if (!value) {
        return {
            state: 'is-empty',
            message: `Optional ${platformLabel} link.`,
            href: '',
        };
    }

    try {
        const url = new URL(value);
        const host = url.hostname.toLowerCase();
        if (!['http:', 'https:'].includes(url.protocol) || !allowedHosts.includes(host)) {
            return {
                state: 'is-invalid',
                message: `Use a valid ${platformLabel} URL.`,
                href: '',
            };
        }
        return {
            state: 'is-valid',
            message: `Ready to publish from ${host}.`,
            href: url.href,
        };
    } catch (error) {
        return {
            state: 'is-invalid',
            message: `Use a valid ${platformLabel} URL.`,
            href: '',
        };
    }
}

function setupWebsiteImageUploads() {
    if (!window.DataTransfer || !HTMLCanvasElement.prototype.toBlob) {
        return;
    }

    const forms = [...new Set([
        ...document.querySelectorAll('[data-website-image-form]'),
        document.getElementById('websiteSettingsForm'),
    ].filter(Boolean))];

    forms.forEach(setupWebsiteImageForm);
}

function setupWebsiteImageForm(form) {
    const status = form.querySelector('[data-image-upload-status]') || document.querySelector('[data-image-upload-status]');
    const imageInputs = [...form.querySelectorAll('input[type="file"]')];
    const maxTotalBytes = 900 * 1024;
    const maxSingleBytes = 850 * 1024;
    const minSingleBytes = 85 * 1024;
    const maxImageEdge = 1800;
    let isSubmittingPreparedForm = false;

    imageInputs.forEach((input) => {
        input.setAttribute('accept', 'image/*');
    });

    form.addEventListener('submit', async (event) => {
        if (isSubmittingPreparedForm) {
            return;
        }

        const selectedFiles = imageInputs.flatMap((input) => [...(input.files || [])].map((file) => ({ input, file })));
        const compressibleFiles = selectedFiles.filter((item) => isCompressibleImage(item.file, item.input.name));

        if (!compressibleFiles.length) {
            return;
        }

        event.preventDefault();
        const targetBytes = clamp(Math.floor(maxTotalBytes / compressibleFiles.length), minSingleBytes, maxSingleBytes);
        const formId = form.getAttribute('id');
        const submitButtons = [
            ...(formId ? [...document.querySelectorAll(`button[form="${formId}"]`)] : []),
            ...form.querySelectorAll('button'),
        ]
            .filter((button) => button.type === 'submit');

        submitButtons.forEach((button) => {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = 'Preparing images...';
        });
        showStatus(status, `Preparing ${compressibleFiles.length} image upload${compressibleFiles.length === 1 ? '' : 's'}...`);

        try {
            const preparedByInput = new Map();
            for (const { input, file } of compressibleFiles) {
                const original = file;
                const prepared = await resizeImageFile(original, targetBytes, maxImageEdge);
                const preparedFile = prepared && prepared.size < original.size ? prepared : original;
                if (!preparedByInput.has(input)) {
                    preparedByInput.set(input, []);
                }
                preparedByInput.get(input).push({ original, prepared: preparedFile });
            }

            preparedByInput.forEach((preparedItems, input) => {
                replaceInputFiles(input, preparedItems);
            });

            for (const input of imageInputs) {
                if (!preparedByInput.has(input) && input.files && input.files.length) {
                    replaceInputFiles(
                        input,
                        [...input.files].map((file) => ({ original: file, prepared: file }))
                    );
                }
            }

            isSubmittingPreparedForm = true;
            showStatus(status, 'Images prepared. Saving website...');
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
        } catch (error) {
            isSubmittingPreparedForm = false;
            submitButtons.forEach((button) => {
                button.disabled = false;
                button.textContent = button.dataset.originalText || 'Save Website';
            });
            showStatus(status, 'One image could not be prepared. Please choose a smaller JPG/PNG image and try again.', true);
        }
    });
}

function isCompressibleImage(file, inputName) {
    if (!file || !file.type.startsWith('image/')) {
        return false;
    }

    if (inputName === 'profile-logo' || file.type === 'image/gif' || file.type === 'image/svg+xml') {
        return false;
    }

    return true;
}

async function resizeImageFile(file, targetBytes, maxImageEdge) {
    const bitmap = await loadImageBitmap(file);
    const sourceWidth = bitmap.width;
    const sourceHeight = bitmap.height;
    const largestSide = Math.max(sourceWidth, sourceHeight);
    let edge = Math.min(maxImageEdge, largestSide);
    let quality = 0.82;
    let bestBlob = null;

    for (let attempt = 0; attempt < 12; attempt += 1) {
        const ratio = edge / largestSide;
        const width = Math.max(1, Math.round(sourceWidth * ratio));
        const height = Math.max(1, Math.round(sourceHeight * ratio));
        const blob = await renderJpeg(bitmap, width, height, quality);

        if (!bestBlob || blob.size < bestBlob.size) {
            bestBlob = blob;
        }
        if (blob.size <= targetBytes) {
            break;
        }
        if (quality > 0.58) {
            quality -= 0.08;
        } else {
            edge = Math.max(720, Math.round(edge * 0.82));
            quality = 0.74;
        }
    }

    if (bitmap.close) {
        bitmap.close();
    }

    if (!bestBlob || bestBlob.size >= file.size) {
        return file;
    }

    return new File([bestBlob], jpgName(file.name), {
        type: 'image/jpeg',
        lastModified: Date.now(),
    });
}

async function loadImageBitmap(file) {
    if ('createImageBitmap' in window) {
        try {
            return await window.createImageBitmap(file, { imageOrientation: 'from-image' });
        } catch (error) {
            return loadImageElement(file);
        }
    }

    return loadImageElement(file);
}

function loadImageElement(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const image = new Image();
        image.onload = () => {
            URL.revokeObjectURL(url);
            resolve(image);
        };
        image.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error('Image load failed'));
        };
        image.src = url;
    });
}

function renderJpeg(source, width, height, quality) {
    return new Promise((resolve, reject) => {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext('2d');

        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, width, height);
        context.drawImage(source, 0, 0, width, height);
        canvas.toBlob(
            (blob) => {
                if (blob) {
                    resolve(blob);
                } else {
                    reject(new Error('Image export failed'));
                }
            },
            'image/jpeg',
            quality
        );
    });
}

function replaceInputFiles(input, preparedItems) {
    const transfer = new DataTransfer();
    const preparedQueue = [...preparedItems];
    [...input.files].forEach((file) => {
        const preparedItemIndex = preparedQueue.findIndex((item) => item.original === file);
        if (preparedItemIndex >= 0) {
            transfer.items.add(preparedQueue[preparedItemIndex].prepared);
            preparedQueue.splice(preparedItemIndex, 1);
        } else {
            transfer.items.add(file);
        }
    });
    input.files = transfer.files;
}

function showStatus(status, message, isError = false) {
    if (!status) {
        return;
    }
    status.textContent = message;
    status.classList.remove('d-none', 'alert-info', 'alert-danger');
    status.classList.add(isError ? 'alert-danger' : 'alert-info');
}

function jpgName(name) {
    return `${name.replace(/\.[^.]+$/, '') || 'website-image'}.jpg`;
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}
