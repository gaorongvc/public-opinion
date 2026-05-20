from typing import List, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from opinion.db import get_db, object_id


app = FastAPI(title="Opinion Monitor")
templates = Jinja2Templates(directory="opinion/templates")
PAGE_SIZE = 20
SENTIMENT_TEXT = {
    "positive": "正向",
    "negative": "负面",
    "neutral": "中性",
}
SOURCE_TEXT = {
    "wechat": "微信公众号",
    "web": "博查搜索",
    "brave": "Brave Search",
    "tophub": "TopHub 热点",
    "toutiao": "头条搜索",
}


def format_datetime(value):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else str(value)


def sentiment_text(value):
    return SENTIMENT_TEXT.get(value, value or "")


def source_text(value):
    return SOURCE_TEXT.get(value, value or "")


def source_list_text(values):
    return "、".join(source_text(value) for value in (values or []))


templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["sentiment_text"] = sentiment_text
templates.env.filters["source_text"] = source_text
templates.env.filters["source_list_text"] = source_list_text


@app.get("/")
def index():
    return RedirectResponse("/plans", status_code=303)


@app.get("/plans")
def plans(request: Request):
    db = get_db()
    records = list(db.plans.find({}))
    return templates.TemplateResponse("plans.html", {"request": request, "plans": records})


@app.get("/plans/new")
def new_plan(request: Request):
    return templates.TemplateResponse("plan_form.html", {"request": request, "plan": {}, "action": "/plans"})


@app.post("/plans")
def create_plan(
    name: str = Form(...),
    kw: str = Form(""),
    any_kw: str = Form(""),
    ex_kw: str = Form(""),
    sources: List[str] = Form(["wechat"]),
    enabled: Optional[str] = Form(None),
):
    db = get_db()
    db.plans.insert_one(_plan_doc(name, kw, any_kw, ex_kw, sources, enabled))
    return RedirectResponse("/plans", status_code=303)


@app.get("/plans/{plan_id}/edit")
def edit_plan(plan_id: str, request: Request):
    db = get_db()
    plan = db.plans.find_one({"_id": object_id(plan_id)}) or db.plans.find_one({"_id": plan_id})
    return templates.TemplateResponse("plan_form.html", {"request": request, "plan": plan, "action": f"/plans/{plan_id}"})


@app.post("/plans/{plan_id}")
def update_plan(
    plan_id: str,
    name: str = Form(...),
    kw: str = Form(""),
    any_kw: str = Form(""),
    ex_kw: str = Form(""),
    sources: List[str] = Form(["wechat"]),
    enabled: Optional[str] = Form(None),
):
    db = get_db()
    plan = db.plans.find_one({"_id": object_id(plan_id)}) or db.plans.find_one({"_id": plan_id})
    if plan:
        db.plans.update_one({"_id": plan["_id"]}, {"$set": _plan_doc(name, kw, any_kw, ex_kw, sources, enabled, update=True)})
    return RedirectResponse("/plans", status_code=303)


@app.post("/plans/{plan_id}/toggle")
def toggle_plan(plan_id: str):
    db = get_db()
    query = {"_id": object_id(plan_id)}
    plan = db.plans.find_one(query) or db.plans.find_one({"_id": plan_id})
    if plan:
        db.plans.update_one({"_id": plan["_id"]}, {"$set": {"enabled": not plan.get("enabled", True)}})
    return RedirectResponse("/plans", status_code=303)


@app.get("/items")
def items(request: Request, page: int = 1):
    db = get_db()
    pagination = _pagination(page)
    records = list(db.items.find({}).sort("published_at", -1).skip(pagination["skip"]).limit(PAGE_SIZE + 1))
    return templates.TemplateResponse(
        "items.html",
        {
            "request": request,
            "items": records[:PAGE_SIZE],
            "page": pagination["page"],
            "has_prev": pagination["page"] > 1,
            "has_next": len(records) > PAGE_SIZE,
            "prev_url": f"/items?page={pagination['page'] - 1}",
            "next_url": f"/items?page={pagination['page'] + 1}",
        },
    )


@app.get("/runs")
def runs(request: Request, page: int = 1):
    db = get_db()
    pagination = _pagination(page)
    records = list(db.runs.find({}).sort("started_at", -1).skip(pagination["skip"]).limit(PAGE_SIZE + 1))
    return templates.TemplateResponse(
        "runs.html",
        {
            "request": request,
            "runs": records[:PAGE_SIZE],
            "page": pagination["page"],
            "has_prev": pagination["page"] > 1,
            "has_next": len(records) > PAGE_SIZE,
            "prev_url": f"/runs?page={pagination['page'] - 1}",
            "next_url": f"/runs?page={pagination['page'] + 1}",
        },
    )


def _pagination(page):
    normalized_page = max(page, 1)
    return {
        "page": normalized_page,
        "skip": (normalized_page - 1) * PAGE_SIZE,
    }


def _plan_doc(name, kw, any_kw, ex_kw, sources, enabled, update=False):
    from opinion.timeutils import utcnow

    doc = {
        "name": name.strip(),
        "kw": kw.strip(),
        "any_kw": any_kw.strip(),
        "ex_kw": ex_kw.strip(),
        "sources": sources or [],
        "enabled": bool(enabled),
        "updated_at": utcnow(),
    }
    if not update:
        doc["created_at"] = utcnow()
    return doc
