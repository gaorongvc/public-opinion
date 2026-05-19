from opinion.classifier import classify_item
from opinion.db import ensure_indexes, get_db
from opinion.formatters import format_item_message
from opinion.keywords import matches_plan
from opinion.notifier import send_to_feishu
from opinion.settings import load_settings
from opinion.sources.bocha import BochaClient
from opinion.sources.brave import BraveSearchClient
from opinion.sources.jizhile import JizhileClient
from opinion.timeutils import utcnow


def run(db=None, source_clients=None, classify=None, send_message=None, settings=None):
    settings = settings or load_settings()
    db = db or get_db()
    ensure_indexes(db)
    source_clients = source_clients or _default_source_clients(settings)
    classify = classify or classify_item
    send_message = send_message or send_to_feishu

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
                raw_items = _search_source(client, source, plan, settings)
            except Exception as exc:
                errors.append(f"{plan.get('name')}:{source}: {exc}")
                continue
            for item in raw_items:
                match_text = " ".join([item.get("title", ""), item.get("content", ""), item.get("summary", "")])
                if not matches_plan(plan, match_text):
                    continue
                collected_count += 1
                stored, inserted = _store_item(db, item, plan_id, plan, classify)
                if inserted and stored.get("related"):
                    try:
                        send_message(format_item_message(stored))
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
        "web": BochaClient(settings.bocha_api_key, endpoint=settings.bocha_endpoint),
        "brave": BraveSearchClient(settings.brave_api_key),
    }


def _search_source(client, source, plan, settings):
    if source == "wechat":
        return client.search(plan, period_days=1, max_pages=settings.jizhile_max_pages)
    if source == "web":
        return client.search(plan, freshness="oneDay", count=settings.bocha_count)
    if source == "brave":
        return client.search(plan, freshness="pd", count=settings.brave_count)
    return client.search(plan)


def _store_item(db, item, plan_id, plan, classify):
    existing = db.items.find_one({"unique_key": item["unique_key"]})
    now = utcnow()
    if existing:
        db.items.update_one(
            {"unique_key": item["unique_key"]},
            {"$addToSet": {"matched_plan_ids": plan_id}, "$set": {"updated_at": now}},
        )
        return db.items.find_one({"unique_key": item["unique_key"]}), False

    classification = classify(item, plan)
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
