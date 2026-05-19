import json
import re


CLASSIFY_PROMPT = """你将获得一条舆情内容和一个监控方案。
请判断内容是否与监控方案相关，并给出情感标签。

监控方案：
- 名称：{plan_name}
- 必须包含：{kw}
- 任一包含：{any_kw}
- 排除词：{ex_kw}

要求：
1. related 为 true 表示内容确实与方案主体相关，不是同名人名、无关公司或泛泛提及。
2. sentiment 只能是 positive、neutral、negative。
3. reason 用中文，控制在 30 字以内，说明为什么相关或不相关。
4. 只返回 JSON，不要输出解释。

内容：
标题：{title}
来源：{source_name}
正文/摘要：{content}
"""


def parse_llm_json(value):
    text = (value or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S)
    if fence_match:
        text = fence_match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    data = json.loads(text)
    return normalize_classification(data)


def normalize_classification(data):
    sentiment = data.get("sentiment") or "neutral"
    if sentiment not in {"positive", "neutral", "negative"}:
        sentiment = "neutral"
    return {
        "related": bool(data.get("related")),
        "sentiment": sentiment,
        "reason": data.get("reason") or ("相关" if data.get("related") else "不相关"),
    }


def classify_item(item, plan, model_name="gpt-4.1"):
    text = f"{item.get('title', '')}{item.get('content', '')}{item.get('summary', '')}"
    if len(text.strip()) < 20:
        return {"related": False, "sentiment": "neutral", "reason": "内容过短"}

    prompt = CLASSIFY_PROMPT.format(
        plan_name=plan.get("name", ""),
        kw=plan.get("kw", ""),
        any_kw=plan.get("any_kw", ""),
        ex_kw=plan.get("ex_kw", ""),
        title=item.get("title", ""),
        source_name=item.get("source_name", ""),
        content=(item.get("content") or item.get("summary") or "")[:4000],
    )
    from grlibs.gpt import GPT

    result = GPT().completion(prompt, model_name=model_name)
    return parse_llm_json(result)

