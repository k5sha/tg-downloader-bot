import re
from typing import Optional

TIKTOK_URL_PATTERNS = [
    r'(https?://(?:vm|vt|www)\.tiktok\.com/[^\s]+)',
    r'(https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+[^\s]*)',
    r'(https?://(?:www\.)?tiktok\.com/t/[\w]+[^\s]*)',
]

def extract_tiktok_url(text: str) -> Optional[str]:
    """Витягує TikTok URL з тексту"""
    for pattern in TIKTOK_URL_PATTERNS:
        if match := re.search(pattern, text, re.IGNORECASE):
            return match.group(1)
    return None