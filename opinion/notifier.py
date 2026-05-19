from opinion.settings import load_settings


def send_to_feishu(message, title=None, webhooks=None):
    from grlibs.feishu_message import Card

    targets = tuple(webhooks or load_settings().feishu_webhooks)
    for webhook in targets:
        Card(webhook).send(message, title=title) if title else Card(webhook).send(message)

