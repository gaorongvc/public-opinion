from opinion.classifier import classify_item
from opinion.db import ensure_indexes, get_db
from opinion.formatters import format_item_message
from opinion.keywords import matches_plan
from opinion.notifier import send_to_feishu
from opinion.settings import load_settings
from opinion.sources.bocha import BochaClient
from opinion.sources.brave import BraveSearchClient
from opinion.sources.jizhile import JizhileClient
from opinion.sources.tophub import TophubClient
from opinion.timeutils import utcnow


JIZHILE_MAX_PAGES = 1
BOCHA_COUNT = 10
BRAVE_COUNT = 10
TOPHUB_COUNT = 10


def run(db=None, settings=None):
    settings = settings or load_settings()
    db = db or get_db()
    ensure_indexes(db)
    source_clients = _default_source_clients(settings)

    started_at = utcnow()
    run_doc = {
        "job": "collect_and_notify_once",
        "status": "running",
        "started_at": started_at,
        "plan_count": 0,
        "collected_count": 0,
        "pushed_count": 0,
        "errors": [],
    }
    run_id = db.runs.insert_one(run_doc).inserted_id
    errors = []
    collected_count = 0
    pushed_count = 0

    plans = list(db.plans.find({"enabled": True}))
    for plan in plans:
        plan_id = str(plan.get("_id"))
        for source in plan.get("sources") or []:
            client = source_clients.get(source)
            if client is None:
                errors.append(f"{plan.get('name')}: unknown source {source}")
                continue
            try:
                raw_items = _search_source(client, source, plan)
            except Exception as exc:
                errors.append(f"{plan.get('name')}:{source}: {exc}")
                continue
            for item in raw_items:
                match_text = " ".join([item.get("title", ""), item.get("content", ""), item.get("summary", "")])
                if not matches_plan(plan, match_text):
                    continue
                collected_count += 1
                stored, inserted = _store_item(db, item, plan_id, plan)
                if inserted and stored.get("related"):
                    try:
                        send_to_feishu(format_item_message(stored))
                    except Exception as exc:
                        errors.append(f"{stored.get('unique_key')}: notify failed: {exc}")
                        continue
                    pushed_count += 1
                    db.items.update_one(
                        {"unique_key": stored["unique_key"]},
                        {"$set": {"notified_at": utcnow(), "updated_at": utcnow()}},
                    )

    status = "success" if not errors else "failed"
    result = {
        "job": "collect_and_notify_once",
        "status": status,
        "started_at": started_at,
        "ended_at": utcnow(),
        "plan_count": len(plans),
        "collected_count": collected_count,
        "pushed_count": pushed_count,
        "errors": errors,
    }
    db.runs.update_one({"_id": run_id}, {"$set": result})
    return result


def _default_source_clients(settings):
    return {
        "wechat": JizhileClient(settings.jizhile_api_key),
        "web": BochaClient(settings.bocha_api_key),
        "brave": BraveSearchClient(settings.brave_api_key),
        "tophub": TophubClient(settings.tophub_token),
    }


def _search_source(client, source, plan):
    if source == "wechat":
        return client.search(plan, period_days=1, max_pages=JIZHILE_MAX_PAGES)
    if source == "web":
        return client.search(plan, freshness="oneDay", count=BOCHA_COUNT)
    if source == "brave":
        return client.search(plan, freshness="pd", count=BRAVE_COUNT)
    if source == "tophub":
        return client.search(plan, count=TOPHUB_COUNT)
    return client.search(plan)


def _store_item(db, item, plan_id, plan):
    existing = db.items.find_one({"unique_key": item["unique_key"]})
    now = utcnow()
    if existing:
        db.items.update_one(
            {"unique_key": item["unique_key"]},
            {"$addToSet": {"matched_plan_ids": plan_id}, "$set": {"updated_at": now}},
        )
        return db.items.find_one({"unique_key": item["unique_key"]}), False

    classification = classify_item(item, plan)
    doc = {
        **item,
        **classification,
        "matched_plan_ids": [plan_id],
        "matched_plan_names": [plan.get("name", "")],
        "created_at": now,
        "updated_at": now,
    }
    db.items.insert_one(doc)
    return doc, True


if __name__ == "__main__":
    print(run())
