import logging
import os
import re
from typing import Optional

import requests
from django.apps import apps

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> Optional[str]:
    """Return a digits/plus only phone or None."""
    if not phone:
        return None
    cleaned = re.sub(r'[^0-9+]', '', phone)
    return cleaned if cleaned else None


def _get_settings():
    """
    Prefer environment variables; fall back to enabled DB config.
    Returns dict with token, phone_number_id, language or None if unavailable.
    """
    env_enabled = os.environ.get('WHATSAPP_ENABLED', '0') == '1'
    env_token = os.environ.get('WHATSAPP_TOKEN')
    env_number_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
    env_lang = os.environ.get('WHATSAPP_LANGUAGE', 'en')
    if env_enabled and env_token and env_number_id:
        return {
            'token': env_token,
            'phone_number_id': env_number_id,
            'language': env_lang,
        }

    try:
        WhatsAppConfig = apps.get_model('portal', 'WhatsAppConfig')
        cfg = WhatsAppConfig.objects.filter(enabled=True, api_token__isnull=False).order_by('-updated_at').first()
        if cfg and cfg.api_token and cfg.phone_number_id:
            return {
                'token': cfg.api_token.strip(),
                'phone_number_id': cfg.phone_number_id.strip(),
                'language': (cfg.default_language or 'en').strip() or 'en',
            }
    except Exception as exc:  # pragma: no cover
        logger.exception("WhatsApp config lookup failed: %s", exc)
    return None


def send_text(to_phone: str, body: str) -> bool:
    """
    Send a WhatsApp text message via WhatsApp Cloud API.
    Returns True on API success, False otherwise. Safe no-op if not configured.
    """
    settings = _get_settings()
    if not settings:
        return False
    to = _normalize_phone(to_phone)
    if not to:
        logger.info("WhatsApp skip: invalid phone for %s", to_phone)
        return False

    url = f"https://graph.facebook.com/v19.0/{settings['phone_number_id']}/messages"
    headers = {
        "Authorization": f"Bearer {settings['token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:1024]},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code >= 400:
            logger.warning("WhatsApp send failed %s: %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:  # pragma: no cover
        logger.exception("WhatsApp send error: %s", exc)
        return False
