from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse
import re

import requests
from retry import retry

from opinion.keywords import keyword_tokens
from opinion.timeutils import parse_datetime, utcnow


class ToutiaoSearchClient:
    endpoint = "https://r.jina.ai/https://so.toutiao.com/search"

    def __init__(self, jina_api_key, endpoint=None):
        self.jina_api_key = jina_api_key
        self.endpoint = endpoint or self.endpoint
        self.request_results = []

    def search(self, plan, period_days=1, count=10):
        if not self.jina_api_key:
            raise RuntimeError("JINA_API_KEY is required for toutiao collection")

        self.request_results = []
        queries = build_toutiao_queries(plan)
        if not queries:
            return []

        limit = max(int(count), 1) if count else 0
        items = []
        seen = set()
        for query in queries:
            max_time = self._search_page_max_time(query)
            params = {
                "dvpf": "pc",
                "source": "input",
                "keyword": query,
                "enable_druid_v2": 1,
                "pd": "synthesis",
                "filter_vendor": "all",
                "index_resource": "all",
                "filter_period": "day",
            }
            if max_time:
                params["max_time"] = max_time
            response = self._request_with_record(query, params, target_selector=".s-result-list")
            for record in extract_toutiao_records(response.text):
                item = map_toutiao_result(record)
                unique_key = item["unique_key"]
                if unique_key in seen:
                    continue
                seen.add(unique_key)
                items.append(item)
                if limit and len(items) >= limit:
                    break
            if limit and len(items) >= limit:
                break
        return items

    def _search_page_max_time(self, query):
        params = {
            "dvpf": "pc",
            "source": "input",
            "keyword": query,
            "enable_druid_v2": 1,
            "page_num": 0,
            "pd": "synthesis",
        }
        response = self._request_with_record(query, params, target_selector=None)
        return extract_max_time(response.text)

    def _request_with_record(self, query, params, target_selector=".s-result-list"):
        try:
            response = self._request(params, target_selector=target_selector)
        except Exception as exc:
            self.request_results.append({"query": query, "request": dict(params), "error": str(exc)})
            raise
        body = response.text
        self.request_results.append({"query": query, "request": dict(params), "response": body})
        return response

    @retry(tries=3, delay=3, logger=None)
    def _request(self, params, target_selector=".s-result-list"):
        headers = {
            "Authorization": f"Bearer {self.jina_api_key}",
            "X-Return-Format": "html",
        }
        if target_selector:
            headers["X-Target-Selector"] = target_selector
        response = requests.get(
            self.endpoint,
            params=params,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response


def build_toutiao_queries(plan):
    kw_tokens = keyword_tokens(plan.get("kw", ""))
    any_tokens = keyword_tokens(plan.get("any_kw", ""))
    if any_tokens:
        return [" ".join([*kw_tokens, token]).strip() for token in any_tokens]
    query = " ".join(kw_tokens).strip()
    return [query] if query else []


def extract_toutiao_records(html):
    records = []
    for chunk in _result_chunks(html or ""):
        record = _extract_result_chunk(chunk)
        if record:
            records.append(record)
    if records:
        return records

    parser = _ToutiaoResultParser()
    parser.feed(html or "")
    return parser.records()


def map_toutiao_result(record):
    url = record.get("url") or ""
    title = record.get("title") or ""
    summary = record.get("summary") or ""
    return {
        "unique_key": f"toutiao:{url}",
        "source_type": "toutiao",
        "source_name": record.get("source_name") or "今日头条",
        "title": title,
        "url": url,
        "content": summary,
        "summary": summary[:300],
        "published_at": _parse_toutiao_time(record.get("published_at")),
        "metrics": {},
        "raw": record,
    }


def extract_max_time(html):
    html = html or ""
    for pattern in (
        r'(?:["\']|&quot;)current_time(?:["\']|&quot;)\s*:\s*(\d{13})',
        r'(?:["\']|&quot;)curTs(?:["\']|&quot;)\s*:\s*(\d{10})',
        r"[?&]max_time=(\d+)",
    ):
        values = [int(value) for value in re.findall(pattern, html)]
        if values:
            return max(values)
    return None


def _result_chunks(html):
    return re.split(r'<div class="result-content" data-i="\d+">', html)[1:]


def _extract_result_chunk(chunk):
    anchors = _extract_anchors(chunk)
    profile_anchor = next((anchor for anchor in anchors if _is_profile_url(anchor["url"])), None)
    content_anchor = next((anchor for anchor in anchors if _is_content_anchor(anchor)), None)
    if not content_anchor:
        return None

    url = _unwrap_toutiao_jump(content_anchor["url"])
    title = _clean_text(content_anchor["text"])
    texts = _extract_texts(chunk)
    summary = _summary_from_chunk(chunk, title) or _summary_from_texts(texts, title)
    source_name = _source_name_from_chunk(chunk, title, summary) or _source_name_from_texts(texts, title, summary, profile_anchor)
    published_at = _published_at_from_texts(texts)
    return {
        "url": url,
        "title": title,
        "summary": summary or title,
        "source_name": source_name,
        "published_at": published_at,
    }


def _extract_anchors(html):
    parser = _AnchorParser()
    parser.feed(html or "")
    return parser.anchors


def _extract_texts(html):
    parser = _TextParser()
    parser.feed(html or "")
    return parser.texts


def _html_fragment_text(html):
    return _clean_text("".join(_extract_texts(html)))


def _is_content_anchor(anchor):
    url = anchor.get("url") or ""
    text = _clean_text(anchor.get("text"))
    return bool(text and _is_result_url(url) and not _is_profile_url(url) and not _is_static_asset_url(url))


def _unwrap_toutiao_jump(url):
    current = url
    for _ in range(5):
        parsed = urlparse(current)
        target = (parse_qs(parsed.query).get("url") or [""])[0]
        if not target:
            break
        current = unquote(target)
    return current


def _is_profile_url(url):
    unwrapped = _unwrap_toutiao_jump(url)
    return "/c/user/" in unwrapped or "%2Fc%2Fuser%2F" in unwrapped.lower()


def _is_static_asset_url(url):
    parsed = urlparse(url)
    return parsed.path.endswith((".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"))


def _summary_from_texts(texts, title):
    seen_title = False
    for text in texts:
        if text == title:
            seen_title = True
            continue
        if not seen_title:
            continue
        if _is_metadata_text(text):
            continue
        return text
    return ""


def _summary_from_chunk(chunk, title):
    index = chunk.find(title)
    if index < 0:
        return ""
    tail = chunk[index + len(title) :]
    match = re.search(r'<span class="[^"]*text-underline-hover[^"]*">(.*?)</span>', tail, flags=re.S)
    if not match:
        return ""
    summary = _html_fragment_text(match.group(1))
    return "" if summary == title or _is_metadata_text(summary) else summary


def _source_name_from_chunk(chunk, title, summary):
    index = chunk.find("cs-source-content")
    if index < 0:
        return ""
    start = chunk.rfind("<", 0, index)
    if start < 0:
        start = index
    for text in _extract_texts(chunk[start : index + 2000]):
        if text in {title, summary} or _is_metadata_text(text):
            continue
        return text
    return ""


def _source_name_from_texts(texts, title, summary, profile_anchor):
    if profile_anchor and profile_anchor.get("text"):
        return _profile_source_name(profile_anchor["text"])
    for index, text in enumerate(texts):
        if text != summary:
            continue
        for candidate in texts[index + 1 :]:
            if candidate == title or _is_metadata_text(candidate):
                continue
            return candidate
    return "今日头条"


def _published_at_from_texts(texts):
    return next((text for text in texts if _looks_like_time_text(text)), "")


def _is_metadata_text(text):
    return _looks_like_time_text(text) or any(token in text for token in ("点赞", "评论", "转发"))


def _looks_like_time_text(text):
    return bool(
        re.search(r"\d+\s*(秒|分钟|小时|天)前", text)
        or text in {"昨天", "前天"}
        or _looks_like_date(text)
    )


def _parse_toutiao_time(value):
    parsed = parse_datetime(value)
    if parsed:
        return parsed
    text = _clean_text(value)
    match = re.match(r"(\d+)\s*(秒|分钟|小时|天)前", text)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "秒":
        delta = timedelta(seconds=amount)
    elif unit == "分钟":
        delta = timedelta(minutes=amount)
    elif unit == "小时":
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    return utcnow() - delta


class _ToutiaoResultParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._items = []
        self._current = None
        self._field = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and _is_result_url(attrs.get("href", "")):
            self._finish_current()
            self._current = {"url": attrs.get("href", ""), "title": "", "summary": "", "source_name": "", "published_at": ""}
            self._field = "title"
            return
        if not self._current:
            return
        if tag == "p":
            self._field = "summary"
        elif tag == "span":
            self._field = "source_name"
        elif tag == "time":
            self._current["published_at"] = attrs.get("datetime") or ""
            self._field = "published_at"

    def handle_endtag(self, tag):
        if tag in {"a", "p", "span", "time"}:
            self._field = None

    def handle_data(self, data):
        if not self._current or not self._field:
            return
        text = _clean_text(data)
        if not text:
            return
        if self._field == "source_name":
            current = self._current.get("source_name", "")
            if not current and not _looks_like_date(text):
                self._current["source_name"] = text
            return
        current = self._current.get(self._field, "")
        self._current[self._field] = _clean_text(" ".join([current, text]))

    def records(self):
        self._finish_current()
        return self._items

    def _finish_current(self):
        if not self._current:
            return
        if self._current.get("url") and self._current.get("title"):
            if not self._current.get("summary"):
                self._current["summary"] = self._current["title"]
            self._items.append(dict(self._current))
        self._current = None
        self._field = None


def _is_result_url(url):
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_text(value):
    return " ".join((value or "").split())


def _looks_like_date(value):
    return bool(re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", value) or re.search(r"\d{1,2}:\d{2}", value))


def _profile_source_name(value):
    text = _clean_text(value)
    text = re.split(r"\d+\s*(?:秒|分钟|小时|天)前", text, maxsplit=1)[0]
    text = text.split("·", 1)[0]
    return _clean_text(text) or "今日头条"


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        self._current = {"url": attrs.get("href", ""), "text": ""}

    def handle_endtag(self, tag):
        if tag == "a" and self._current:
            self._current["text"] = _clean_text(self._current["text"])
            self.anchors.append(self._current)
            self._current = None

    def handle_data(self, data):
        if self._current is not None:
            self._current["text"] = _clean_text(" ".join([self._current["text"], data]))


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts = []
        self._ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data):
        if self._ignored_depth:
            return
        text = _clean_text(data)
        if text:
            self.texts.append(text)


if __name__ == "__main__":
    import os

    from opinion.env import load_env

    load_env()
    client = ToutiaoSearchClient(os.getenv("JINA_API_KEY", ""))
    plan = {
        "kw": os.getenv("OPINION_TEST_KW", "高榕创投"),
        "any_kw": os.getenv("OPINION_TEST_ANY_KW", ""),
        "ex_kw": os.getenv("OPINION_TEST_EX_KW", ""),
    }
    items = client.search(plan, period_days=int(os.getenv("OPINION_TEST_PERIOD_DAYS", "1")), count=10)
    for item in items:
        print(item["source_name"], item["title"], item["url"])
