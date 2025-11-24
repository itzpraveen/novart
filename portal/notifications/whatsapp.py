import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_ENABLED = os.environ.get('WHATSAPP_ENABLED', '0') == '1'


def _configured() -> bool:
    return bool(WHATSAPP_ENABLED and WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID)


def _normalize_phone(phone: str) -> Optional[str]:
    """Return a digits/plus only phone or None."""
    if not phone:
        return None
    cleaned = re.sub(r'[^0-9+]', '', phone)
    return cleaned if cleaned else None


def send_text(to_phone: str, body: str) -> bool:
    """
    Send a WhatsApp text message via WhatsApp Cloud API.
    Returns True on API success, False otherwise. Safe no-op if not configured.
    """
    if not _configured():
        return False
    to = _normalize_phone(to_phone)
    if not to:
        logger.info("WhatsApp skip: invalid phone for %s", to_phone)
        return False

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
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

