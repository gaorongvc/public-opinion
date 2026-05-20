import requests

from opinion.timeutils import parse_datetime


class JizhileClient:
    endpoint = "https://www.dajiala.com/fbmain/monitor/v3/kw_search"

    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, plan, period_days=1, max_pages=1):
        if not self.api_key:
            raise RuntimeError("JZL_API_KEY is required for wechat collection")

        items = []
        for page in range(1, max_pages + 1):
            payload = {
                "kw": plan.get("kw", ""),
                "sort_type": 2,
                "mode": 3,
                "period": period_days,
                "page": page,
                "key": self.api_key,
                "any_kw": plan.get("any_kw", ""),
                "ex_kw": plan.get("ex_kw", ""),
                "verifycode": "",
                "type": 1,
            }
            response = requests.post(self.endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            response.raise_for_status()
            body = response.json()
            if body.get("code") not in (0, None):
                raise RuntimeError(f"Jizhile API error: {body.get('msg') or body.get('message') or body.get('code')}")
            records = body.get("data") or []
            if not records:
                break
            items.extend(map_article(record) for record in records)
        return items


def map_article(record):
    url = record.get("url") or record.get("short_link") or ""
    content = record.get("content") or record.get("digest") or ""
    return {
        "unique_key": f"wechat:{url}",
        "source_type": "wechat",
        "source_name": record.get("wx_name") or record.get("mp_nickname") or "微信公众号",
        "title": record.get("title") or "",
        "url": url,
        "content": content,
        "summary": content[:300],
        "published_at": parse_datetime(record.get("publish_time") or record.get("post_time") or record.get("post_time_str")),
        "metrics": {
            "read": record.get("read"),
            "praise": record.get("praise"),
            "looking": record.get("looking"),
        },
        "raw": record,
    }


if __name__ == "__main__":
    import os

    from opinion.env import load_env

    load_env()
    client = JizhileClient(os.getenv("JZL_API_KEY", ""))
    plan = {
        "kw": os.getenv("OPINION_TEST_KW", "高榕"),
        "any_kw": os.getenv("OPINION_TEST_ANY_KW", "融资"),
        "ex_kw": os.getenv("OPINION_TEST_EX_KW", ""),
    }
    items = client.search(plan, period_days=1, max_pages=1)
    for item in items:
        print(item["source_name"], item["title"], item["url"])
