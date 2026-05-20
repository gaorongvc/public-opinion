from datetime import timedelta

import requests
from retry import retry

from opinion.keywords import keyword_tokens
from opinion.timeutils import parse_datetime, utcnow


class TophubClient:
    endpoint = "https://api.tophubdata.com/search"

    def __init__(self, token, endpoint=None):
        self.token = token
        self.endpoint = endpoint or self.endpoint
        self.request_results = []

    def search(self, plan, count=10, hashid="", fresh_hours=24):
        if not self.token:
            raise RuntimeError("TOPHUB_TOKEN is required for tophub collection")

        self.request_results = []
        queries = build_tophub_queries(plan)
        if not queries:
            return []

        limit = max(int(count), 1) if count else 0
        cutoff = utcnow() - timedelta(hours=fresh_hours) if fresh_hours else None
        items = []
        for query in queries:
            params = {"q": query, "p": 1}
            if hashid:
                params["hashid"] = hashid
            response = self._request_with_record(query, params)
            body = response.json()
            for record in extract_tophub_records(body):
                item = map_hot_item(record)
                if not is_fresh_item(item, cutoff):
                    continue
                items.append(item)
                if limit and len(items) >= limit:
                    break
            if limit and len(items) >= limit:
                break
        return items

    def _request_with_record(self, query, params):
        try:
            response = self._request(params)
        except Exception as exc:
            self.request_results.append({"query": query, "request": dict(params), "error": str(exc)})
            raise
        body = response.json()
        self.request_results.append({"query": query, "request": dict(params), "response": body})
        return response

    @retry(tries=3, delay=3, logger=None)
    def _request(self, params):
        response = requests.get(
            self.endpoint,
            params=params,
            headers={"Authorization": self.token},
            timeout=30,
        )
        response.raise_for_status()
        return response


def build_tophub_queries(plan):
    kw_tokens = keyword_tokens(plan.get("kw", ""))
    any_tokens = keyword_tokens(plan.get("any_kw", ""))
    if any_tokens:
        return [" ".join([*kw_tokens, token]).strip() for token in any_tokens]
    query = " ".join(kw_tokens).strip()
    return [query] if query else []


def extract_tophub_records(body):
    data = body.get("data") or {}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or data.get("list") or []
    return []


def is_fresh_item(item, cutoff):
    if cutoff is None:
        return True
    published_at = item.get("published_at")
    return bool(published_at and published_at >= cutoff)


def map_hot_item(record):
    url = record.get("url") or ""
    title = record.get("title") or ""
    description = record.get("description") or ""
    source_name = record.get("source") or record.get("node") or "TopHub"
    published_at = parse_datetime(record.get("time") or record.get("created_at") or record.get("date"))
    unique_value = url or f"{source_name}:{title}:{record.get('time') or ''}"
    return {
        "unique_key": f"tophub:{unique_value}",
        "source_type": "tophub",
        "source_name": source_name,
        "title": title,
        "url": url,
        "content": description,
        "summary": description[:300],
        "published_at": published_at,
        "metrics": {"hot": record.get("hot")},
        "raw": record,
    }


if __name__ == "__main__":
    import os

    from opinion.env import load_env

    load_env()
    client = TophubClient(os.getenv("TOPHUB_TOKEN", ""))
    plan = {
        "kw": os.getenv("OPINION_TEST_KW", "高榕创投"),
        "any_kw": os.getenv("OPINION_TEST_ANY_KW", ""),
        "ex_kw": os.getenv("OPINION_TEST_EX_KW", ""),
    }
    items = client.search(plan, count=10)
    for item in items:
        print(item["source_name"], item["title"], item["url"])
