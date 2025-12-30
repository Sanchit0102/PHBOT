# ==========================================================================================================
# extractor.py (FIXED JSON + duration extraction)
# ==========================================================================================================

import json
import requests
from bs4 import BeautifulSoup

class StreamingURLExtractor:
    def __init__(self, video_url: str):
        self.video_url = video_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

    def fetch_page(self) -> str:
        r = self.session.get(self.video_url, timeout=20)
        r.raise_for_status()
        return r.text

    def extract_duration(self) -> str:
        html = self.fetch_page()
        soup = BeautifulSoup(html, "lxml")
        d = soup.select_one("span.duration")
        return d.get_text(strip=True) if d else "N/A"

    def extract_streaming_urls(self, use_browser=False):
        html = self.fetch_page()

        key = '"mediaDefinitions":'
        idx = html.find(key)
        if idx == -1:
            return []

        idx += len(key)
        depth = 0
        start = end = None

        for i in range(idx, len(html)):
            if html[i] == "[":
                depth += 1
                if start is None:
                    start = i
            elif html[i] == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if not start or not end:
            return []

        try:
            return json.loads(html[start:end])
        except Exception:
            return []

    def resolve_stream_url(self, url: str) -> str:
        try:
            r = self.session.head(url, allow_redirects=True, timeout=10)
            return r.url
        except Exception:
            return url
