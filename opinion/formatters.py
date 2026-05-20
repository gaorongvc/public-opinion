from collections import OrderedDict


SENTIMENT_LABELS = {
    "positive": ("正面", "green"),
    "neutral": ("中性", "grey"),
    "negative": ("负面", "red"),
}


def format_item_message(item):
    label, color = SENTIMENT_LABELS.get(item.get("sentiment"), SENTIMENT_LABELS["neutral"])
    title = item.get("title") or "无标题"
    url = item.get("url") or ""
    source_name = item.get("source_name") or item.get("source_type") or "未知来源"
    reason = item.get("reason") or ""
    return f"""<font color={color}>**{label}**</font>【{source_name}】
[{title}]({url})
{reason}
"""


def format_daily_summary(items, start_at, end_at):
    total = len(items)
    positive = [item for item in items if item.get("sentiment") == "positive"]
    neutral = [item for item in items if item.get("sentiment") == "neutral"]
    negative = [item for item in items if item.get("sentiment") == "negative"]

    def pct(count):
        return int(count / total * 100) if total else 0

    sources = "，".join(OrderedDict.fromkeys(item.get("source_name", "") for item in items if item.get("source_name")))[:80]
    sources_line = f"参与媒体主要有{sources}等" if sources else "暂无媒体来源"
    return f"""{start_at.strftime("%Y年%m月%d日%H点")}-{end_at.strftime("%Y年%m月%d日%H点")}
舆情有效声量 {total} 条
正面{len(positive)}条，占比{pct(len(positive))}%
中性{len(neutral)}条，占比{pct(len(neutral))}%
敏感{len(negative)}条，占比{pct(len(negative))}%
{sources_line}

重要舆情回顾：
【正面】
{_build_items(positive)}

【中性】
{_build_items(neutral)}

【敏感】
{_build_items(negative)}
"""


def _build_items(items):
    seen = set()
    lines = []
    for item in items:
        title = item.get("title") or "无标题"
        if title in seen:
            continue
        seen.add(title)
        source_name = item.get("source_name") or "未知来源"
        url = item.get("url") or ""
        reason = item.get("reason") or ""
        lines.append(f"【{source_name}】[{title}]({url})\n{reason}")
    return "\n".join(lines) if lines else "无"

