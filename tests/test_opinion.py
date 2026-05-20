from datetime import datetime, timezone

import pytest

from opinion.classifier import parse_llm_json
from opinion.formatters import format_daily_summary, format_item_message
from opinion.jobs.collect_and_notify_once import run as collect_and_notify_once
from opinion.jobs.daily_summary import run as daily_summary
from opinion.keywords import build_search_query, keyword_tokens, matches_plan
from opinion.notifier import FeishuNotifyError, ensure_feishu_success
from opinion.sources.bocha import BochaClient
from opinion.sources.brave import BraveSearchClient
from opinion.sources.jizhile import JizhileClient
from opinion.sources.tophub import TophubClient, build_tophub_queries


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

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


def test_jizhile_client_maps_wechat_articles_and_payload():
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
    client = JizhileClient(api_key="key", session=session)
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, period_days=1, max_pages=1)

    assert session.calls[0][1]["json"]["kw"] == "高榕"
    assert items[0]["source_type"] == "wechat"
    assert items[0]["source_name"] == "投资号"
    assert items[0]["metrics"]["read"] == 123
    assert items[0]["unique_key"] == "wechat:https://mp.weixin.qq.com/s/abc"


def test_bocha_client_maps_web_pages():
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
    client = BochaClient(api_key="bocha-key", session=session)
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, freshness="oneDay", count=10)

    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer bocha-key"
    assert session.calls[0][1]["json"]["summary"] is True
    assert items[0]["source_type"] == "web"
    assert items[0]["source_name"] == "Example"
    assert items[0]["unique_key"] == "web:https://example.com/a"


def test_brave_client_maps_web_results_and_uses_subscription_header():
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
    client = BraveSearchClient(api_key="brave-key", session=session)
    items = client.search({"kw": "高榕", "any_kw": "融资", "ex_kw": ""}, freshness="pd", count=10)

    assert session.calls[0][1]["headers"]["X-Subscription-Token"] == "brave-key"
    assert session.calls[0][1]["params"]["q"] == "高榕 (融资)"
    assert session.calls[0][1]["params"]["result_filter"] == "web"
    assert items[0]["source_type"] == "brave"
    assert items[0]["source_name"] == "Example"
    assert items[0]["unique_key"] == "brave:https://example.com/brave"


def test_tophub_client_maps_hot_items_and_uses_authorization_header():
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
    client = TophubClient(token="tophub-token", session=session)
    items = client.search({"kw": "高榕", "any_kw": "融资 募资", "ex_kw": "招聘"}, count=10)

    assert session.calls[0][1]["headers"]["Authorization"] == "tophub-token"
    assert [call[1]["params"]["q"] for call in session.calls] == ["高榕 融资", "高榕 募资"]
    assert items[0]["source_type"] == "tophub"
    assert items[0]["source_name"] == "微博热搜"
    assert items[0]["metrics"]["hot"] == 567890
    assert items[0]["unique_key"] == "tophub:https://example.com/tophub"


def test_tophub_queries_use_kw_plus_single_any_kw_without_operators():
    plan = {"kw": "高榕 资本", "any_kw": "融资 投资", "ex_kw": "招聘"}
    assert build_tophub_queries(plan) == ["高榕 资本 融资", "高榕 资本 投资"]


def test_parse_llm_json_accepts_fenced_json():
    data = parse_llm_json('```json\n{"related": true, "sentiment": "negative", "reason": "涉及负面舆情"}\n```')
    assert data == {"related": True, "sentiment": "negative", "reason": "涉及负面舆情"}


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


def test_collect_and_notify_once_writes_items_runs_and_sends_related_item():
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
        def search(self, plan, period_days=1, max_pages=1):
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

    result = collect_and_notify_once(
        db=db,
        source_clients={"wechat": FakeWechat()},
        classify=lambda item, plan: {"related": True, "sentiment": "positive", "reason": "高榕参与融资"},
        send_message=lambda message: sent.append(message),
    )

    assert result["status"] == "success"
    assert result["collected_count"] == 1
    assert result["pushed_count"] == 1
    assert db.items.find_one({"unique_key": "wechat:https://mp.weixin.qq.com/s/abc"})["related"] is True
    assert db.runs.docs[-1]["job"] == "collect_and_notify_once"
    assert "高榕参与融资" in sent[0]


def test_collect_and_notify_once_does_not_send_existing_related_item():
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

    result = collect_and_notify_once(
        db=db,
        source_clients={"brave": FakeBrave()},
        classify=lambda item, plan: {"related": True, "sentiment": "positive", "reason": "高榕参与融资"},
        send_message=lambda message: sent.append(message),
    )

    assert result["status"] == "success"
    assert result["collected_count"] == 1
    assert result["pushed_count"] == 0
    assert sent == []
    assert db.items.find_one({"unique_key": "brave:https://example.com/a"})["matched_plan_ids"] == ["plan-1"]


def test_collect_and_notify_once_records_notify_error_without_marking_notified():
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
        def search(self, plan, period_days=1, max_pages=1):
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

    result = collect_and_notify_once(
        db=db,
        source_clients={"wechat": FakeWechat()},
        classify=lambda item, plan: {"related": True, "sentiment": "positive", "reason": "高榕参与融资"},
        send_message=lambda message: (_ for _ in ()).throw(FeishuNotifyError("frequency limited")),
    )

    stored = db.items.find_one({"unique_key": "wechat:https://mp.weixin.qq.com/s/fail"})
    assert result["status"] == "failed"
    assert result["pushed_count"] == 0
    assert "notify failed: frequency limited" in result["errors"][0]
    assert "notified_at" not in stored


def test_daily_summary_reads_last_24_hours_and_sends_report():
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

    result = daily_summary(db=db, now=now, send_message=lambda message, title=None: sent.append((title, message)))

    assert result["status"] == "success"
    assert result["item_count"] == 1
    assert sent[0][0] == "舆情日报 2026-05-19"
    assert "敏感1条，占比100%" in sent[0][1]
