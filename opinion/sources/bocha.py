import requests

from opinion.keywords import build_search_query
from opinion.timeutils import parse_datetime


class BochaClient:
    def __init__(self, api_key, endpoint="https://api.bochaai.com/v1/web-search", session=None):
        self.api_key = api_key
        self.endpoint = endpoint
        self.session = session or requests

    def search(self, plan, freshness="oneDay", count=10):
        if not self.api_key:
            raise RuntimeError("BOCHA_API_KEY is required for web collection")

        query = build_search_query(plan)
        if not query:
            return []
        payload = {
            "query": query,
            "freshness": freshness,
            "summary": True,
            "count": count,
        }
        response = self.session.post(
            self.endpoint,
            json=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        records = (((body.get("data") or {}).get("webPages") or {}).get("value") or [])
        return [map_web_page(record) for record in records]


def map_web_page(record):
    url = record.get("url") or record.get("link") or ""
    summary = record.get("summary") or record.get("snippet") or record.get("content") or ""
    return {
        "unique_key": f"web:{url}",
        "source_type": "web",
        "source_name": record.get("siteName") or record.get("site_name") or record.get("displayUrl") or "网页",
        "title": record.get("name") or record.get("title") or "",
        "url": url,
        "content": summary,
        "summary": summary,
        "published_at": parse_datetime(record.get("datePublished") or record.get("date_published")),
        "metrics": {},
        "raw": record,
    }

