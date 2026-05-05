document.addEventListener('DOMContentLoaded', () => {
    setupWebsiteImageUploads();
});

function setupWebsiteImageUploads() {
    const form = document.getElementById('websiteSettingsForm');
    if (!form || !window.DataTransfer || !HTMLCanvasElement.prototype.toBlob) {
        return;
    }

    const status = document.querySelector('[data-image-upload-status]');
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

        const selectedInputs = imageInputs.filter((input) => input.files && input.files[0]);
        const compressibleInputs = selectedInputs.filter((input) => isCompressibleImage(input.files[0], input.name));

        if (!compressibleInputs.length) {
            return;
        }

        event.preventDefault();
        const targetBytes = clamp(Math.floor(maxTotalBytes / compressibleInputs.length), minSingleBytes, maxSingleBytes);
        const submitButtons = [...document.querySelectorAll('button[form="websiteSettingsForm"], #websiteSettingsForm button')]
            .filter((button) => button.type === 'submit');

        submitButtons.forEach((button) => {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = 'Preparing images...';
        });
        showStatus(status, `Preparing ${compressibleInputs.length} image upload${compressibleInputs.length === 1 ? '' : 's'}...`);

        try {
            for (const input of compressibleInputs) {
                const original = input.files[0];
                const prepared = await resizeImageFile(original, targetBytes, maxImageEdge);
                if (prepared && prepared.size < original.size) {
                    replaceInputFile(input, prepared);
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

function replaceInputFile(input, file) {
    const transfer = new DataTransfer();
    transfer.items.add(file);
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
