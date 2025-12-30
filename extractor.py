# extractor.py (FIXED, production-safe)

import json
import requests

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

    def extract_streaming_urls(self):
        html = self.fetch_page()

        key = '"mediaDefinitions":'
        idx = html.find(key)
        if idx == -1:
            return []

        idx += len(key)
        bracket = 0
        start = None
        end = None

        for i in range(idx, len(html)):
            if html[i] == '[':
                bracket += 1
                if start is None:
                    start = i
            elif html[i] == ']':
                bracket -= 1
                if bracket == 0:
                    end = i + 1
                    break

        if start is None or end is None:
            return []

        raw_json = html[start:end]

        try:
            return json.loads(raw_json)
        except Exception:
            return []

    def resolve_stream_url(self, url: str) -> str:
        try:
            r = self.session.head(url, allow_redirects=True, timeout=10)
            return r.url
        except Exception:
            return url
