import os
from dataclasses import dataclass

from opinion.env import load_env


DEFAULT_FEISHU_WEBHOOKS = (
    # "https://open.feishu.cn/open-apis/bot/v2/hook/a5d55c55-3462-4ab9-835f-5ac774ea0e36",
    "https://open.feishu.cn/open-apis/bot/v2/hook/2b3e21a4-f348-4183-adf7-fd2205368696",
)


@dataclass(frozen=True)
class Settings:
    jizhile_api_key: str = ""
    bocha_api_key: str = ""
    brave_api_key: str = ""
    tophub_token: str = ""
    feishu_webhooks: tuple[str, ...] = DEFAULT_FEISHU_WEBHOOKS


def _split_env_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def load_settings() -> Settings:
    load_env()
    webhooks = _split_env_list(os.getenv("FEISHU_WEBHOOKS", ""))
    return Settings(
        jizhile_api_key=os.getenv("JZL_API_KEY", "JZL9145b9c50fc2d48f"),
        bocha_api_key=os.getenv("BOCHA_API_KEY", ""),
        brave_api_key=os.getenv("BRAVE_API_KEY", ""),
        tophub_token=os.getenv("TOPHUB_TOKEN", ""),
        feishu_webhooks=webhooks or DEFAULT_FEISHU_WEBHOOKS,
    )
