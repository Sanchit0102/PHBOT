import re
import json
import requests
from typing import List, Dict

class StreamingURLExtractor:
    def __init__(self, video_url: str):
        self.video_url = video_url
        self.session = requests.Session()

    def fetch_page(self):
        r = self.session.get(self.video_url, timeout=20)
        r.raise_for_status()
        return r.text

    def extract_streaming_urls(self) -> List[Dict]:
        html = self.fetch_page()
        match = re.search(r'"mediaDefinitions"\s*:\s*(\[.*?\])', html, re.DOTALL)
        if not match:
            return []
        return json.loads(match.group(1))

    def resolve_stream_url(self, url: str) -> str:
        try:
            r = self.session.head(url, allow_redirects=True, timeout=10)
            return r.url
        except Exception:
            return url
