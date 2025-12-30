import requests
from bs4 import BeautifulSoup

BASE = "https://de.pornhub.org"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def search(query, limit=10):
    r = requests.get(f"{BASE}/video/search?search={query}", headers=HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    results = []

    for v in soup.select("li.pcVideoListItem")[:limit]:
        a = v.select_one("a")
        img = v.select_one("img")
        if not a or not img:
            continue

        results.append({
            "title": a.get("title") or "Video",
            "url": BASE + a["href"],
            "poster": img.get("data-src") or img.get("src"),
            "duration": v.select_one(".duration").text.strip() if v.select_one(".duration") else "N/A"
        })

    return results
