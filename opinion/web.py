from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from opinion.db import get_db, object_id


app = FastAPI(title="Opinion Monitor")
templates = Jinja2Templates(directory="opinion/templates")


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
    sources: list[str] = Form(["wechat", "web"]),
    enabled: str | None = Form(None),
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
    sources: list[str] = Form(["wechat", "web"]),
    enabled: str | None = Form(None),
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
def items(request: Request):
    db = get_db()
    records = list(db.items.find({}).sort("created_at", -1).limit(200))
    return templates.TemplateResponse("items.html", {"request": request, "items": records})


@app.get("/runs")
def runs(request: Request):
    db = get_db()
    records = list(db.runs.find({}).sort("started_at", -1).limit(100))
    return templates.TemplateResponse("runs.html", {"request": request, "runs": records})


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
