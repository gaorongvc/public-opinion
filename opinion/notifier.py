from opinion.settings import load_settings


class FeishuNotifyError(RuntimeError):
    pass


def ensure_feishu_success(response, webhook=""):
    if response is None or not isinstance(response, dict):
        return
    for key in ("code", "StatusCode"):
        if key in response and str(response[key]) != "0":
            message = response.get("msg") or response.get("StatusMessage") or "unknown error"
            raise FeishuNotifyError(f"Feishu webhook {webhook} returned {key}={response[key]}: {message}")


def send_to_feishu(message, title=None, webhooks=None):
    from grlibs.feishu_message import Card

    targets = tuple(webhooks or load_settings().feishu_webhooks)
    responses = []
    for webhook in targets:
        response = Card(webhook).send(message, title=title) if title else Card(webhook).send(message)
        ensure_feishu_success(response, webhook)
        responses.append(response)
    return responses
