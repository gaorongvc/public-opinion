from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value
        return value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, timezone.utc)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed = datetime.strptime(normalized[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed = datetime.strptime(normalized[:10], "%Y-%m-%d")
                except ValueError:
                    return None
        if parsed.tzinfo:
            return parsed
        return parsed.replace(tzinfo=timezone.utc)
    return None

