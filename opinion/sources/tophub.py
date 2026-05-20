import requests

from opinion.keywords import keyword_tokens
from opinion.timeutils import parse_datetime


class TophubClient:
    endpoint = "https://api.tophubdata.com/search"

    def __init__(self, token, endpoint=None):
        self.token = token
        self.endpoint = endpoint or self.endpoint

    def search(self, plan, page=1, max_pages=1, count=10, hashid=""):
        if not self.token:
            raise RuntimeError("TOPHUB_TOKEN is required for tophub collection")

        queries = build_tophub_queries(plan)
        if not queries:
            return []

        limit = max(int(count), 1) if count else 0
        records = []
        for query in queries:
            for current_page in range(int(page), int(page) + max(int(max_pages), 1)):
                params = {"q": query, "p": current_page}
                if hashid:
                    params["hashid"] = hashid
                response = requests.get(
                    self.endpoint,
                    params=params,
                    headers={"Authorization": self.token},
                    timeout=30,
                )
                response.raise_for_status()
                body = response.json()
                records.extend(body.get("data", {}).get('items', []) or [])
                if limit and len(records) >= limit:
                    break
            if limit and len(records) >= limit:
                break
        selected = records[:limit] if limit else records
        return [map_hot_item(record) for record in selected]


def build_tophub_queries(plan):
    kw_tokens = keyword_tokens(plan.get("kw", ""))
    any_tokens = keyword_tokens(plan.get("any_kw", ""))
    if any_tokens:
        return [" ".join([*kw_tokens, token]).strip() for token in any_tokens]
    query = " ".join(kw_tokens).strip()
    return [query] if query else []


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
