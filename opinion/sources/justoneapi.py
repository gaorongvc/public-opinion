from datetime import timedelta, timezone

import requests
from retry import retry

from opinion.keywords import keyword_tokens
from opinion.timeutils import parse_datetime, utcnow


DEFAULT_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")


class JustOneApiClient:
    endpoint = "https://api.justoneapi.com/api/search/v1"

    def __init__(self, token, endpoint=None, timezone=DEFAULT_TIMEZONE):
        self.token = token
        self.endpoint = endpoint or self.endpoint
        self.timezone = timezone
        self.request_results = []

    def search(self, plan, count=10, hours=6):
        if not self.token:
            raise RuntimeError("JUSTONEAPI_TOKEN is required for justoneapi collection")

        self.request_results = []
        queries = build_justoneapi_queries(plan)
        if not queries:
            return []

        start, end = default_time_window(hours, timezone=self.timezone)
        limit = max(int(count), 1) if count else 0
        items = []
        for query in queries:
            params = {
                "token": self.token,
                "keyword": query,
                "source": "ALL",
                "start": start,
                "end": end,
            }
            response = self._request_with_record(query, params)
            body = response.json()
            _raise_for_business_error(body)

            records = (((body.get("data") or {}).get("list")) or [])
            for record in records:
                items.append(map_cross_platform_item(record))
                if limit and len(items) >= limit:
                    break
            if limit and len(items) >= limit:
                break
        return items

    def _request_with_record(self, query, params):
        safe_params = {key: value for key, value in params.items() if key != "token"}
        try:
            response = self._request(params)
        except Exception as exc:
            self.request_results.append({"query": query, "request": safe_params, "error": str(exc)})
            raise
        body = response.json()
        self.request_results.append({"query": query, "request": safe_params, "response": body})
        return response

    @retry(tries=3, delay=3, logger=None)
    def _request(self, params):
        response = requests.get(
            self.endpoint,
            params=params,
            headers={"Accept": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        return response


def build_justoneapi_queries(plan):
    kw_tokens = keyword_tokens(plan.get("kw", ""))
    any_tokens = keyword_tokens(plan.get("any_kw", ""))
    if any_tokens:
        return [" ".join([*kw_tokens, token]).strip() for token in any_tokens]
    query = " ".join(kw_tokens).strip()
    return [query] if query else []


def default_time_window(hours=6, timezone=DEFAULT_TIMEZONE):
    end = utcnow().astimezone(timezone)
    start = end - timedelta(hours=hours)
    return _format_api_time(start), _format_api_time(end)


def map_cross_platform_item(record):
    url = record.get("url") or ""
    title = record.get("title") or ""
    content = record.get("content") or ""
    source_name = record.get("sourceName") or record.get("source_name") or "Just One API"
    author = record.get("author") or {}
    unique_value = url or f"{source_name}:{title}:{record.get('createTime') or ''}"
    return {
        "unique_key": f"justoneapi:{unique_value}",
        "source_type": "justoneapi",
        "source_name": source_name,
        "title": title,
        "url": url,
        "content": content,
        "summary": content[:300],
        "published_at": parse_datetime(record.get("createTime") or record.get("create_time")),
        "metrics": {
            "author_nickname": author.get("nickname"),
            "author_username": author.get("username"),
            "author_id": author.get("id"),
        },
        "raw": record,
    }


def _format_api_time(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _raise_for_business_error(body):
    if body.get("code") in (0, None):
        return
    message = body.get("message") or body.get("msg") or body.get("code")
    raise RuntimeError(f"JustOneAPI error: {message}")


if __name__ == "__main__":
    import os

    from opinion.env import load_env

    load_env()
    client = JustOneApiClient(os.getenv("JUSTONEAPI_TOKEN", ""))
    plan = {
        "kw": os.getenv("OPINION_TEST_KW", ""),
        "any_kw": os.getenv("OPINION_TEST_ANY_KW", "高榕创投 高榕资本"),
        "ex_kw": os.getenv("OPINION_TEST_EX_KW", ""),
    }
    items = client.search(plan, count=10)
    for item in items:
        print(item["source_name"], item["title"], item["url"])
