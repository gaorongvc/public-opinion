import re


def keyword_tokens(value):
    if not value:
        return []
    return [token for token in re.split(r"[\s|,，]+", value.strip()) if token]


def matches_plan(plan, text):
    text = text or ""
    kw_tokens = keyword_tokens(plan.get("kw", ""))
    any_tokens = keyword_tokens(plan.get("any_kw", ""))
    ex_tokens = keyword_tokens(plan.get("ex_kw", ""))

    if kw_tokens and not all(token in text for token in kw_tokens):
        return False
    if any_tokens and not any(token in text for token in any_tokens):
        return False
    if ex_tokens and any(token in text for token in ex_tokens):
        return False
    return bool(kw_tokens or any_tokens)


def build_search_query(plan):
    tokens = keyword_tokens(plan.get("kw", "")) + keyword_tokens(plan.get("any_kw", ""))
    return " ".join(tokens)

