from datetime import datetime, timezone

import pytest

import opinion.jobs.collect_and_notify_once as collect_job
import opinion.jobs.daily_summary as daily_summary_job
import opinion.sources.bocha as bocha_source
import opinion.sources.brave as brave_source
import opinion.sources.jizhile as jizhile_source
import opinion.sources.toutiao as toutiao_source
import opinion.sources.tophub as tophub_source
import opinion.classifier as classifier
from opinion.classifier import parse_llm_json
from opinion.formatters import format_daily_summary, format_item_message
from opinion.keywords import build_search_query, keyword_tokens, matches_plan
from opinion.notifier import FeishuNotifyError, ensure_feishu_success
from opinion.sources.bocha import BochaClient
from opinion.sources.brave import BraveSearchClient
from opinion.sources.jizhile import JizhileClient
from opinion.sources.toutiao import ToutiaoSearchClient, build_toutiao_queries
from opinion.sources.tophub import TophubClient, build_tophub_queries


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    @property
    def text(self):
        return self.payload if isinstance(self.payload, str) else ""

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


class SequenceSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))


class FlakySession:
    def __init__(self, payload, failures=2):
        self.payload = payload
        self.failures = failures
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._response()

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._response()

    def _response(self):
        if len(self.calls) <= self.failures:
            raise TimeoutError("temporary timeout")
        return FakeResponse(self.payload)


class InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.next_id = 1

    def find(self, query=None):
        return [doc for doc in self.docs if self._matches(doc, query or {})]

    def find_one(self, query):
        for doc in self.find(query):
            return doc
        return None

    def insert_one(self, doc):
        stored = dict(doc)
        if "_id" not in stored:
            stored["_id"] = f"id-{self.next_id}"
            self.next_id += 1
        self.docs.append(stored)
        return InsertResult(stored["_id"])

    def update_one(self, query, update, upsert=False):
        doc = self.find_one(query)
        if doc is None and upsert:
            doc = dict(query)
            self.docs.append(doc)
        if doc is None:
            return None
        if "$set" in update:
            doc.update(update["$set"])
        if "$addToSet" in update:
            for key, value in update["$addToSet"].items():
                doc.setdefault(key, [])
                if value not in doc[key]:
                    doc[key].append(value)
        return None

    def create_index(self, *args, **kwargs):
        return None

    def _matches(self, doc, query):
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict):
                if "$gte" in expected and not (value >= expected["$gte"]):
                    return False
                if "$lte" in expected and not (value <= expected["$lte"]):
                    return False
            elif value != expected:
                return False
        return True


class FakeDb:
    def __init__(self):
        self.plans = FakeCollection()
        self.items = FakeCollection()
        self.runs = FakeCollection()


def test_keyword_tokens_split_pipe_space_and_newline():
    assert keyword_tokens("高榕|博茨 微\n高格") == ["高榕", "博茨", "微", "高格"]


def test_matches_plan_requires_kw_any_and_exclusion():
    plan = {"kw": "高榕 资本", "any_kw": "融资 投资", "ex_kw": "招聘"}
    assert matches_plan(plan, "高榕资本完成新一轮融资")
    assert not matches_plan(plan, "高榕资本发布招聘信息")
    assert not matches_plan(plan, "高榕资本发布年度报告")


def test_build_search_query_uses_google_compatible_boolean_logic():
    plan = {"kw": "高榕 资本", "any_kw": "融资 投资", "ex_kw": "招聘 离职"}
    assert build_search_query(plan) == '高榕 资本 (融资 OR 投资) -招聘 -离职'


def test_jizhile_client_maps_wechat_articles_and_payload(monkeypatch):
    session = FakeSession(
        {
            "code": 0,
            "data": [
                {
                    "title": "高榕资本消息",
                    "url": "https://mp.weixin.qq.com/s/abc",
                    "content": "高榕资本参与融资",
                    "publish_time": 1710000000,
                    "wx_name": "投资号",
                    "read": 123,
                }
            ],
        }
    )
    monkeypatch.setattr(jizhile_source, "requests", session)

    client = JizhileClient(api_key="key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, period_days=1)

    assert session.calls[0][1]["json"]["kw"] == "高榕"
    assert items[0]["source_type"] == "wechat"
    assert items[0]["source_name"] == "投资号"
    assert items[0]["metrics"]["read"] == 123
    assert items[0]["unique_key"] == "wechat:https://mp.weixin.qq.com/s/abc"


def test_jizhile_client_retries_request_three_times(monkeypatch):
    session = FlakySession(
        {
            "code": 0,
            "data": [
                {
                    "title": "高榕资本消息",
                    "url": "https://mp.weixin.qq.com/s/retry",
                    "content": "高榕资本参与融资",
                    "publish_time": 1710000000,
                    "wx_name": "投资号",
                }
            ],
        }
    )
    monkeypatch.setattr(jizhile_source, "requests", session)

    client = JizhileClient(api_key="key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, period_days=1)

    assert len(session.calls) == 3
    assert items[0]["unique_key"] == "wechat:https://mp.weixin.qq.com/s/retry"


def test_jizhile_client_only_requests_first_page(monkeypatch):
    session = FakeSession(
        {
            "code": 0,
            "data": [
                {
                    "title": "高榕资本消息",
                    "url": "https://mp.weixin.qq.com/s/page-one",
                    "content": "高榕资本参与融资",
                }
            ],
        }
    )
    monkeypatch.setattr(jizhile_source, "requests", session)

    client = JizhileClient(api_key="key")
    client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, period_days=1)

    assert len(session.calls) == 1
    assert session.calls[0][1]["json"]["page"] == 1


def test_bocha_client_maps_web_pages(monkeypatch):
    session = FakeSession(
        {
            "data": {
                "webPages": {
                    "value": [
                        {
                            "name": "高榕资本新闻",
                            "url": "https://example.com/a",
                            "summary": "高榕资本参与融资",
                            "snippet": "融资消息",
                            "siteName": "Example",
                            "datePublished": "2026-05-18",
                        }
                    ]
                }
            }
        }
    )
    monkeypatch.setattr(bocha_source, "requests", session)

    client = BochaClient(api_key="bocha-key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, freshness="oneDay", count=10)

    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer bocha-key"
    assert session.calls[0][1]["json"]["summary"] is True
    assert items[0]["source_type"] == "web"
    assert items[0]["source_name"] == "Example"
    assert items[0]["unique_key"] == "web:https://example.com/a"


def test_bocha_client_retries_request_three_times(monkeypatch):
    session = FlakySession(
        {
            "data": {
                "webPages": {
                    "value": [
                        {
                            "name": "高榕资本新闻",
                            "url": "https://example.com/bocha-retry",
                            "summary": "高榕资本参与融资",
                            "siteName": "Example",
                        }
                    ]
                }
            }
        }
    )
    monkeypatch.setattr(bocha_source, "requests", session)

    client = BochaClient(api_key="bocha-key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, freshness="oneDay", count=10)

    assert len(session.calls) == 3
    assert items[0]["unique_key"] == "web:https://example.com/bocha-retry"


def test_brave_client_maps_web_results_and_uses_subscription_header(monkeypatch):
    session = FakeSession(
        {
            "web": {
                "results": [
                    {
                        "title": "高榕资本新闻",
                        "url": "https://example.com/brave",
                        "description": "高榕资本参与融资",
                        "page_age": "2026-05-18T10:00:00",
                        "profile": {"name": "Example"},
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(brave_source, "requests", session)

    client = BraveSearchClient(api_key="brave-key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, freshness="pd", count=10)

    assert session.calls[0][1]["headers"]["X-Subscription-Token"] == "brave-key"
    assert session.calls[0][1]["params"]["q"] == "高榕 (融资)"
    assert session.calls[0][1]["params"]["result_filter"] == "web"
    assert items[0]["source_type"] == "brave"
    assert items[0]["source_name"] == "Example"
    assert items[0]["unique_key"] == "brave:https://example.com/brave"


def test_brave_client_retries_request_three_times(monkeypatch):
    session = FlakySession(
        {
            "web": {
                "results": [
                    {
                        "title": "高榕资本新闻",
                        "url": "https://example.com/brave-retry",
                        "description": "高榕资本参与融资",
                        "profile": {"name": "Example"},
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(brave_source, "requests", session)

    client = BraveSearchClient(api_key="brave-key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, freshness="pd", count=10)

    assert len(session.calls) == 3
    assert items[0]["unique_key"] == "brave:https://example.com/brave-retry"


def test_toutiao_client_maps_jina_html_and_uses_reader_headers(monkeypatch):
    session = SequenceSession(
        [
            """
            <div class="s-result-list">
              <a href="/search?filter_period=all&max_time=1779287545&min_time=0">1</a>
            </div>
            """,
            """
            <div class="s-result-list">
              <div class="result-card">
                <a href="https://www.toutiao.com/article/123">高榕资本新闻</a>
                <span>今日头条</span>
                <p>高榕资本参与融资</p>
                <time datetime="2026-05-20T09:00:00+08:00">2026-05-20</time>
              </div>
            </div>
            """,
        ]
    )
    monkeypatch.setattr(toutiao_source, "requests", session)
    monkeypatch.setattr(toutiao_source, "utcnow", lambda: datetime(2026, 5, 20, tzinfo=timezone.utc))

    client = ToutiaoSearchClient(jina_api_key="jina-key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, period_days=1, count=10)

    assert session.calls[0][0] == "https://r.jina.ai/https://so.toutiao.com/search"
    assert session.calls[0][1]["params"]["keyword"] == "高榕 融资"
    assert "filter_period" not in session.calls[0][1]["params"]
    assert session.calls[1][1]["headers"]["Authorization"] == "Bearer jina-key"
    assert session.calls[1][1]["headers"]["X-Return-Format"] == "html"
    assert session.calls[1][1]["headers"]["X-Target-Selector"] == ".s-result-list"
    assert session.calls[1][1]["params"]["keyword"] == "高榕 融资"
    assert session.calls[1][1]["params"]["filter_period"] == "day"
    assert session.calls[1][1]["params"]["max_time"] == 1779287545
    assert "min_time" not in session.calls[1][1]["params"]
    assert items[0]["source_type"] == "toutiao"
    assert items[0]["source_name"] == "今日头条"
    assert items[0]["summary"] == "高榕资本参与融资"
    assert items[0]["unique_key"] == "toutiao:https://www.toutiao.com/article/123"


def test_toutiao_client_extracts_current_time_as_max_time():
    html = """
    <script>
      window.__SSR_HYDRATED_DATA__ = {"curTs":1779331727,"current_time":1779331727356};
    </script>
    """

    assert toutiao_source.extract_max_time(html) == 1779331727356


def test_toutiao_client_uses_current_time_from_full_search_page(monkeypatch):
    session = SequenceSession(
        [
            """
            <html><script>
              window.__SSR_HYDRATED_DATA__ = {"curTs":1779331727,"current_time":1779331727356};
            </script></html>
            """,
            """
            <div class="s-result-list">
              <a href="https://www.toutiao.com/article/456">普京访华</a>
              <p>普京访华欢迎仪式</p>
            </div>
            """,
        ]
    )
    monkeypatch.setattr(toutiao_source, "requests", session)

    client = ToutiaoSearchClient(jina_api_key="jina-key")
    client.search({"kw": "普京", "any_kw": "", "ex_kw": ""}, period_days=1, count=10)

    assert "X-Target-Selector" not in session.calls[0][1]["headers"]
    assert session.calls[1][1]["headers"]["X-Target-Selector"] == ".s-result-list"
    assert session.calls[1][1]["params"]["max_time"] == 1779331727356


def test_toutiao_client_retries_request_three_times(monkeypatch):
    session = FlakySession(
        """
        <div class="s-result-list">
          <article>
            <a href="https://www.toutiao.com/article/retry">高榕资本新闻</a>
            <p>高榕资本参与融资</p>
          </article>
        </div>
        """
    )
    monkeypatch.setattr(toutiao_source, "requests", session)
    monkeypatch.setattr(toutiao_source, "utcnow", lambda: datetime(2026, 5, 20, tzinfo=timezone.utc))

    client = ToutiaoSearchClient(jina_api_key="jina-key")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, period_days=1, count=10)

    assert len(session.calls) == 4
    assert "filter_period" not in session.calls[2][1]["params"]
    assert session.calls[3][1]["params"]["filter_period"] == "day"
    assert items[0]["unique_key"] == "toutiao:https://www.toutiao.com/article/retry"


def test_toutiao_client_skips_author_profile_link_and_unwraps_jump_url(monkeypatch):
    session = FakeSession(
        """
        <div class="s-result-list">
          <div class="result-content" data-i="0">
            <a href="https://sou.toutiao.com/search/jump?url=https%3A%2F%2Fwww.toutiao.com%2Fc%2Fuser%2F3237381370288883%2F&aid=4916">
              <span>拼到思维</span>
              <span>14小时前</span>
              <span>·</span>
              <span>头条新锐创作者</span>
            </a>
            <a href="https://sou.toutiao.com/search/jump?url=https%3A%2F%2Fwww.toutiao.com%2Fa1865656332658816%2F%3Fsource%3Dinput&aid=4916">本轮融资由高榕创投联合领投</a>
            <span>2点赞</span>
          </div>
        </div>
        """
    )
    monkeypatch.setattr(toutiao_source, "requests", session)
    monkeypatch.setattr(toutiao_source, "utcnow", lambda: datetime(2026, 5, 20, tzinfo=timezone.utc))

    client = ToutiaoSearchClient(jina_api_key="jina-key")
    items = client.search({"kw": "高榕创投", "any_kw": "", "ex_kw": ""}, period_days=1, count=10)

    assert items[0]["source_name"] == "拼到思维"
    assert items[0]["title"] == "本轮融资由高榕创投联合领投"
    assert items[0]["url"] == "https://www.toutiao.com/a1865656332658816/?source=input"
    assert items[0]["unique_key"] == "toutiao:https://www.toutiao.com/a1865656332658816/?source=input"


def test_toutiao_client_extracts_summary_and_source_from_result_card(monkeypatch):
    session = FakeSession(
        """
        <div class="s-result-list">
          <div class="result-content" data-i="1">
            <div data-log-click="{&quot;pos&quot;:&quot;title&quot;}">
              <a href="https://sou.toutiao.com/search/jump?url=http%3A%2F%2Fwww.toutiao.com%2Fa7641761524045890063%2F%3Fchannel%3D&aid=4916">解决中小企业出海支付难题</a>
            </div>
            <span class="text-underline-hover"><em>高榕创投</em>是最大机构股东，持股约12.83%</span>
            <div class="cs-source-content">
              <span class="text-ellipsis">时代财经</span>
              <span class="text-ellipsis">12小时前</span>
            </div>
          </div>
        </div>
        """
    )
    monkeypatch.setattr(toutiao_source, "requests", session)
    monkeypatch.setattr(toutiao_source, "utcnow", lambda: datetime(2026, 5, 20, tzinfo=timezone.utc))

    client = ToutiaoSearchClient(jina_api_key="jina-key")
    items = client.search({"kw": "高榕创投", "any_kw": "", "ex_kw": ""}, period_days=1, count=10)

    assert items[0]["source_name"] == "时代财经"
    assert items[0]["summary"] == "高榕创投是最大机构股东，持股约12.83%"
    assert items[0]["published_at"] is not None


def test_toutiao_queries_use_kw_plus_single_any_kw_without_operators():
    plan = {"kw": "高榕 资本", "any_kw": "融资 投资", "ex_kw": "招聘"}
    assert build_toutiao_queries(plan) == ["高榕 资本 融资", "高榕 资本 投资"]


def test_tophub_client_maps_hot_items_and_uses_authorization_header(monkeypatch):
    session = FakeSession(
        {
            "data": [
                {
                    "title": "高榕资本新闻",
                    "url": "https://example.com/tophub",
                    "source": "微博热搜",
                    "hot": 567890,
                    "time": "2026-05-18 10:00:00",
                }
            ],
            "page": 1,
            "total": 1,
        }
    )
    monkeypatch.setattr(tophub_source, "requests", session)
    monkeypatch.setattr(tophub_source, "utcnow", lambda: datetime(2026, 5, 18, 11, tzinfo=timezone.utc))

    client = TophubClient(token="tophub-token")
    items = client.search({"kw": "高榕", "any_kw": "融资 募资", "ex_kw": "招聘"}, count=10)

    assert session.calls[0][1]["headers"]["Authorization"] == "tophub-token"
    assert [call[1]["params"]["q"] for call in session.calls] == ["高榕 融资", "高榕 募资"]
    assert items[0]["source_type"] == "tophub"
    assert items[0]["source_name"] == "微博热搜"
    assert items[0]["metrics"]["hot"] == 567890
    assert items[0]["unique_key"] == "tophub:https://example.com/tophub"


def test_tophub_client_retries_request_three_times(monkeypatch):
    session = FlakySession(
        {
            "data": [
                {
                    "title": "高榕资本新闻",
                    "url": "https://example.com/tophub-retry",
                    "source": "微博热搜",
                    "time": "2026-05-18 10:00:00",
                }
            ],
            "page": 1,
            "total": 1,
        }
    )
    monkeypatch.setattr(tophub_source, "requests", session)
    monkeypatch.setattr(tophub_source, "utcnow", lambda: datetime(2026, 5, 18, 11, tzinfo=timezone.utc))

    client = TophubClient(token="tophub-token")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, count=10)

    assert len(session.calls) == 3
    assert items[0]["unique_key"] == "tophub:https://example.com/tophub-retry"


def test_tophub_client_only_requests_first_page(monkeypatch):
    session = FakeSession({"data": [], "page": 1, "total": 0})
    monkeypatch.setattr(tophub_source, "requests", session)
    monkeypatch.setattr(tophub_source, "utcnow", lambda: datetime(2026, 5, 18, 11, tzinfo=timezone.utc))

    client = TophubClient(token="tophub-token")
    client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, count=10)

    assert len(session.calls) == 1
    assert session.calls[0][1]["params"]["p"] == 1


def test_tophub_client_filters_items_older_than_24_hours(monkeypatch):
    session = FakeSession(
        {
            "data": {
                "items": [
                    {
                        "title": "高榕资本今日新闻",
                        "url": "https://example.com/tophub/new",
                        "source": "微博热搜",
                        "time": "2026-05-19 09:30:00",
                    },
                    {
                        "title": "高榕资本历史新闻",
                        "url": "https://example.com/tophub/old",
                        "source": "微博热搜",
                        "time": "2026-05-18 08:59:59",
                    },
                    {
                        "title": "高榕资本无时间新闻",
                        "url": "https://example.com/tophub/unknown",
                        "source": "微博热搜",
                    },
                ]
            },
            "page": 1,
            "total": 3,
        }
    )
    monkeypatch.setattr(tophub_source, "requests", session)
    monkeypatch.setattr(tophub_source, "utcnow", lambda: datetime(2026, 5, 19, 9, tzinfo=timezone.utc))

    client = TophubClient(token="tophub-token")
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, count=10)

    assert [item["url"] for item in items] == ["https://example.com/tophub/new"]


def test_tophub_queries_use_kw_plus_single_any_kw_without_operators():
    plan = {"kw": "高榕 资本", "any_kw": "融资 投资", "ex_kw": "招聘"}
    assert build_tophub_queries(plan) == ["高榕 资本 融资", "高榕 资本 投资"]


def test_parse_llm_json_accepts_fenced_json():
    data = parse_llm_json('```json\n{"related": true, "sentiment": "negative", "reason": "涉及负面舆情"}\n```')
    assert data == {"related": True, "sentiment": "negative", "reason": "涉及负面舆情"}


def test_classify_item_uses_lm_chat(monkeypatch):
    calls = []

    class FakeLM:
        def __init__(self, model):
            self.model = model
            calls.append(("init", model))

        def chat(self, messages, to_json=True):
            calls.append(("chat", messages, to_json))
            return '{"related": true, "sentiment": "positive", "reason": "高榕参与融资"}'

    monkeypatch.setattr(classifier, "LM", FakeLM)

    result = classifier.classify_item(
        {
            "title": "高榕资本消息",
            "source_name": "投资号",
            "content": "高榕资本参与医药魔方新一轮融资，市场反馈较好。",
            "summary": "",
        },
        {"name": "高榕品牌关键词", "kw": "高榕", "any_kw": "融资", "ex_kw": ""},
        model_name="openai/gpt-4.1",
    )

    assert result == {"related": True, "sentiment": "positive", "reason": "高榕参与融资"}
    assert calls[0] == ("init", "openai/gpt-4.1")
    assert calls[1][2] is False
    assert calls[1][1][0]["role"] == "user"
    assert "高榕资本消息" in calls[1][1][0]["content"]


def test_format_item_message_matches_feishu_card_style():
    message = format_item_message(
        {
            "sentiment": "positive",
            "source_name": "腾讯自选股",
            "title": "医药魔方融资",
            "url": "https://example.com/news",
            "reason": "高榕参与本轮融资。",
        }
    )
    assert "<font color=green>**正面**</font>" in message
    assert "【腾讯自选股】" in message
    assert "[医药魔方融资](https://example.com/news)" in message


def test_format_daily_summary_handles_zero_items():
    content = format_daily_summary([], datetime(2026, 5, 18, tzinfo=timezone.utc), datetime(2026, 5, 19, tzinfo=timezone.utc))
    assert "有效声量 0 条" in content
    assert "正面0条，占比0%" in content


def test_ensure_feishu_success_raises_for_non_zero_business_code():
    with pytest.raises(FeishuNotifyError, match="frequency limited"):
        ensure_feishu_success({"code": 11232, "msg": "frequency limited"}, webhook="https://example.com/hook")


def test_collect_and_notify_once_writes_items_runs_and_sends_related_item(monkeypatch):
    db = FakeDb()
    db.plans.insert_one(
        {
            "_id": "plan-1",
            "name": "高榕品牌关键词",
            "kw": "高榕",
            "any_kw": "融资",
            "ex_kw": "",
            "sources": ["wechat"],
            "enabled": True,
        }
    )

    class FakeWechat:
        def search(self, plan, period_days=1):
            return [
                {
                    "unique_key": "wechat:https://mp.weixin.qq.com/s/abc",
                    "source_type": "wechat",
                    "source_name": "投资号",
                    "title": "高榕资本消息",
                    "url": "https://mp.weixin.qq.com/s/abc",
                    "content": "高榕资本参与融资",
                    "summary": "高榕资本参与融资",
                    "published_at": None,
                    "metrics": {},
                    "raw": {},
                }
            ]

    sent = []
    monkeypatch.setattr(collect_job, "load_settings", lambda: object())
    monkeypatch.setattr(collect_job, "_default_source_clients", lambda settings: {"wechat": FakeWechat()})
    monkeypatch.setattr(
        collect_job,
        "classify_item",
        lambda item, plan: {"related": True, "sentiment": "positive", "reason": "高榕参与融资"},
    )
    monkeypatch.setattr(collect_job, "send_to_feishu", sent.append)

    result = collect_job.run(db=db)

    assert result["status"] == "success"
    assert result["collected_count"] == 1
    assert result["pushed_count"] == 1
    assert db.items.find_one({"unique_key": "wechat:https://mp.weixin.qq.com/s/abc"})["related"] is True
    assert db.runs.docs[-1]["job"] == "collect_and_notify_once"
    assert "高榕参与融资" in sent[0]


def test_collect_and_notify_once_stores_request_results_on_run(monkeypatch):
    db = FakeDb()
    db.plans.insert_one(
        {
            "_id": "plan-1",
            "name": "高榕品牌关键词",
            "kw": "高榕",
            "any_kw": "融资",
            "ex_kw": "",
            "sources": ["brave"],
            "enabled": True,
        }
    )

    class FakeBrave:
        request_results = [
            {
                "query": "高榕 (融资)",
                "request": {"q": "高榕 (融资)", "freshness": "pd", "count": 10},
                "response": {
                    "web": {
                        "results": [
                            {
                                "title": "高榕资本融资消息",
                                "url": "https://example.com/matched",
                            }
                        ]
                    }
                },
            }
        ]

        def search(self, plan, freshness="pd", count=10):
            return [
                {
                    "unique_key": "brave:https://example.com/matched",
                    "source_type": "brave",
                    "source_name": "Example",
                    "title": "高榕资本融资消息",
                    "url": "https://example.com/matched",
                    "content": "高榕资本参与融资",
                    "summary": "高榕资本参与融资",
                    "published_at": datetime(2026, 5, 20, tzinfo=timezone.utc),
                    "metrics": {"rank": 1},
                    "raw": {"large": "payload"},
                },
                {
                    "unique_key": "brave:https://example.com/ignored",
                    "source_type": "brave",
                    "source_name": "Example",
                    "title": "无关新闻",
                    "url": "https://example.com/ignored",
                    "content": "无关内容",
                    "summary": "无关内容",
                    "published_at": None,
                    "metrics": {},
                    "raw": {"large": "payload"},
                },
            ]

    monkeypatch.setattr(collect_job, "load_settings", lambda: object())
    monkeypatch.setattr(collect_job, "_default_source_clients", lambda settings: {"brave": FakeBrave()})
    monkeypatch.setattr(
        collect_job,
        "classify_item",
        lambda item, plan: {"related": False, "sentiment": "neutral", "reason": "测试"},
    )
    monkeypatch.setattr(collect_job, "send_to_feishu", lambda message: None)

    result = collect_job.run(db=db)
    request_result = result["request_results"][0]

    assert "source_results" not in result
    assert request_result["plan_id"] == "plan-1"
    assert request_result["plan_name"] == "高榕品牌关键词"
    assert request_result["source"] == "brave"
    assert request_result["query"] == "高榕 (融资)"
    assert request_result["request"] == {"q": "高榕 (融资)", "freshness": "pd", "count": 10}
    assert request_result["response"]["web"]["results"][0]["url"] == "https://example.com/matched"
    assert db.runs.docs[-1]["request_results"] == result["request_results"]


def test_collect_and_notify_once_does_not_send_existing_related_item(monkeypatch):
    db = FakeDb()
    db.plans.insert_one(
        {
            "_id": "plan-1",
            "name": "高榕品牌关键词",
            "kw": "高榕",
            "any_kw": "融资",
            "ex_kw": "",
            "sources": ["brave"],
            "enabled": True,
        }
    )
    db.items.insert_one(
        {
            "unique_key": "brave:https://example.com/a",
            "source_type": "brave",
            "source_name": "Example",
            "title": "高榕资本消息",
            "url": "https://example.com/a",
            "content": "高榕资本参与融资",
            "summary": "高榕资本参与融资",
            "related": True,
            "sentiment": "positive",
            "reason": "高榕参与融资",
            "matched_plan_ids": [],
        }
    )

    class FakeBrave:
        def search(self, plan, freshness="pd", count=10):
            return [
                {
                    "unique_key": "brave:https://example.com/a",
                    "source_type": "brave",
                    "source_name": "Example",
                    "title": "高榕资本消息",
                    "url": "https://example.com/a",
                    "content": "高榕资本参与融资",
                    "summary": "高榕资本参与融资",
                    "published_at": None,
                    "metrics": {},
                    "raw": {},
                }
            ]

    sent = []
    monkeypatch.setattr(collect_job, "load_settings", lambda: object())
    monkeypatch.setattr(collect_job, "_default_source_clients", lambda settings: {"brave": FakeBrave()})
    monkeypatch.setattr(
        collect_job,
        "classify_item",
        lambda item, plan: {"related": True, "sentiment": "positive", "reason": "高榕参与融资"},
    )
    monkeypatch.setattr(collect_job, "send_to_feishu", sent.append)

    result = collect_job.run(db=db)

    assert result["status"] == "success"
    assert result["collected_count"] == 1
    assert result["pushed_count"] == 0
    assert sent == []
    assert db.items.find_one({"unique_key": "brave:https://example.com/a"})["matched_plan_ids"] == ["plan-1"]


def test_collect_and_notify_once_marks_partial_success_when_one_source_times_out(monkeypatch):
    db = FakeDb()
    db.plans.insert_one(
        {
            "_id": "plan-1",
            "name": "高榕品牌关键词",
            "kw": "高榕",
            "any_kw": "融资",
            "ex_kw": "",
            "sources": ["wechat", "brave"],
            "enabled": True,
        }
    )

    class TimeoutWechat:
        def search(self, plan, period_days=1):
            raise TimeoutError("Read timed out")

    class FakeBrave:
        def search(self, plan, freshness="pd", count=10):
            return [
                {
                    "unique_key": "brave:https://example.com/a",
                    "source_type": "brave",
                    "source_name": "Example",
                    "title": "高榕资本消息",
                    "url": "https://example.com/a",
                    "content": "高榕资本参与融资",
                    "summary": "高榕资本参与融资",
                    "published_at": None,
                    "metrics": {},
                    "raw": {},
                }
            ]

    sent = []
    monkeypatch.setattr(collect_job, "load_settings", lambda: object())
    monkeypatch.setattr(collect_job, "_default_source_clients", lambda settings: {"wechat": TimeoutWechat(), "brave": FakeBrave()})
    monkeypatch.setattr(
        collect_job,
        "classify_item",
        lambda item, plan: {"related": False, "sentiment": "neutral", "reason": "测试"},
    )
    monkeypatch.setattr(collect_job, "send_to_feishu", sent.append)

    result = collect_job.run(db=db)

    assert result["status"] == "partial_success"
    assert result["collected_count"] == 1
    assert result["errors"] == []
    assert "高榕品牌关键词:wechat: Read timed out" in result["warnings"][0]


def test_collect_and_notify_once_records_notify_error_without_marking_notified(monkeypatch):
    db = FakeDb()
    db.plans.insert_one(
        {
            "_id": "plan-1",
            "name": "高榕品牌关键词",
            "kw": "高榕",
            "any_kw": "融资",
            "ex_kw": "",
            "sources": ["wechat"],
            "enabled": True,
        }
    )

    class FakeWechat:
        def search(self, plan, period_days=1):
            return [
                {
                    "unique_key": "wechat:https://mp.weixin.qq.com/s/fail",
                    "source_type": "wechat",
                    "source_name": "投资号",
                    "title": "高榕资本消息",
                    "url": "https://mp.weixin.qq.com/s/fail",
                    "content": "高榕资本参与融资",
                    "summary": "高榕资本参与融资",
                    "published_at": None,
                    "metrics": {},
                    "raw": {},
                }
            ]

    def send_failure(message):
        raise FeishuNotifyError("frequency limited")

    monkeypatch.setattr(collect_job, "load_settings", lambda: object())
    monkeypatch.setattr(collect_job, "_default_source_clients", lambda settings: {"wechat": FakeWechat()})
    monkeypatch.setattr(
        collect_job,
        "classify_item",
        lambda item, plan: {"related": True, "sentiment": "positive", "reason": "高榕参与融资"},
    )
    monkeypatch.setattr(collect_job, "send_to_feishu", send_failure)

    result = collect_job.run(db=db)

    stored = db.items.find_one({"unique_key": "wechat:https://mp.weixin.qq.com/s/fail"})
    assert result["status"] == "failed"
    assert result["pushed_count"] == 0
    assert "notify failed: frequency limited" in result["errors"][0]
    assert "notified_at" not in stored


def test_daily_summary_reads_last_24_hours_and_sends_report(monkeypatch):
    db = FakeDb()
    now = datetime(2026, 5, 19, tzinfo=timezone.utc)
    db.items.insert_one(
        {
            "unique_key": "web:https://example.com/a",
            "created_at": datetime(2026, 5, 18, 1, tzinfo=timezone.utc),
            "related": True,
            "sentiment": "negative",
            "source_name": "Example",
            "title": "高榕资本消息",
            "url": "https://example.com/a",
            "reason": "涉及高榕负面消息",
        }
    )
    sent = []
    monkeypatch.setattr(daily_summary_job, "send_to_feishu", lambda message, title=None: sent.append((title, message)))

    result = daily_summary_job.run(db=db, now=now)

    assert result["status"] == "success"
    assert result["item_count"] == 1
    assert sent[0][0] == "舆情日报 2026-05-19"
    assert "敏感1条，占比100%" in sent[0][1]
