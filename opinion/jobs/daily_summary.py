from datetime import timedelta

from opinion.db import ensure_indexes, get_db
from opinion.formatters import format_daily_summary
from opinion.notifier import send_to_feishu
from opinion.timeutils import utcnow


def run(db=None, now=None):
    db = db or get_db()
    ensure_indexes(db)
    now = now or utcnow()
    start_at = now - timedelta(days=1)

    run_doc = {
        "job": "daily_summary",
        "status": "running",
        "started_at": utcnow(),
        "errors": [],
    }
    run_id = db.runs.insert_one(run_doc).inserted_id
    errors = []
    items = list(db.items.find({"created_at": {"$gte": start_at}, "related": True}))
    content = format_daily_summary(items, start_at, now)
    try:
        send_to_feishu(content, title=f"舆情日报 {now.strftime('%Y-%m-%d')}")
    except TypeError:
        send_to_feishu(content)
    except Exception as exc:
        errors.append(f"notify failed: {exc}")

    result = {
        "job": "daily_summary",
        "status": "success" if not errors else "failed",
        "started_at": run_doc["started_at"],
        "ended_at": utcnow(),
        "item_count": len(items),
        "pushed_count": 0 if errors else 1,
        "errors": errors,
    }
    db.runs.update_one({"_id": run_id}, {"$set": result})
    return result


if __name__ == "__main__":
    run()
