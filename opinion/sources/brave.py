from urllib.parse import urlparse

import requests
from retry import retry

from opinion.keywords import build_search_query
from opinion.timeutils import parse_datetime


class BraveSearchClient:
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key, endpoint=None):
        self.api_key = api_key
        self.endpoint = endpoint or self.endpoint

    def search(self, plan, freshness="pd", count=10):
        if not self.api_key:
            raise RuntimeError("BRAVE_API_KEY is required for brave collection")

        query = build_search_query(plan)
        if not query:
            return []
        params = {
            "q": query,
            # "country": "CN",
            # "search_lang": "zh-hans",
            "count": min(max(int(count), 1), 10),
            # "safesearch": "strict",
            "freshness": freshness,
            "result_filter": "web",
        }
        response = self._request(params)
        body = response.json()
        records = ((body.get("web") or {}).get("results") or [])
        return [map_web_result(record) for record in records]

    @retry(tries=3, delay=3, logger=None)
    def _request(self, params):
        response = requests.get(
            self.endpoint,
            params=params,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response


def map_web_result(record):
    url = record.get("url") or ""
    summary = record.get("description") or record.get("snippet") or ""
    profile = record.get("profile") or {}
    source_name = profile.get("name") or _hostname(url) or "Brave Search"
    return {
        "unique_key": f"brave:{url}",
        "source_type": "brave",
        "source_name": source_name,
        "title": record.get("title") or "",
        "url": url,
        "content": summary,
        "summary": summary,
        "published_at": parse_datetime(record.get("page_age") or record.get("age")),
        "metrics": {},
        "raw": record,
    }


def _hostname(url):
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


if __name__ == "__main__":
    import os

    from opinion.env import load_env

    load_env()
    client = BraveSearchClient(os.getenv("BRAVE_API_KEY", ""))
    plan = {
        "kw": os.getenv("OPINION_TEST_KW", "高榕 创投"),
        "any_kw": os.getenv("OPINION_TEST_ANY_KW", "融资 募资"),
        "ex_kw": os.getenv("OPINION_TEST_EX_KW", ""),
    }
    items = client.search(plan, freshness=os.getenv("OPINION_TEST_FRESHNESS", "pd"), count=10)
    for item in items:
        print(item["source_name"], item["title"], item["url"])
