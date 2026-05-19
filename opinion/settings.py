import os
from dataclasses import dataclass


DEFAULT_FEISHU_WEBHOOKS = (
    # "https://open.feishu.cn/open-apis/bot/v2/hook/a5d55c55-3462-4ab9-835f-5ac774ea0e36",
    "https://open.feishu.cn/open-apis/bot/v2/hook/2b3e21a4-f348-4183-adf7-fd2205368696",
)


@dataclass(frozen=True)
class Settings:
    jizhile_api_key: str = ""
    bocha_api_key: str = ""
    bocha_endpoint: str = "https://api.bochaai.com/v1/web-search"
    feishu_webhooks: tuple[str, ...] = DEFAULT_FEISHU_WEBHOOKS
    jizhile_max_pages: int = 1
    bocha_count: int = 10


def _split_env_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def load_settings() -> Settings:
    webhooks = _split_env_list(os.getenv("FEISHU_WEBHOOKS", ""))
    return Settings(
        jizhile_api_key=os.getenv("JZL_API_KEY", "JZL9145b9c50fc2d48f"),
        bocha_api_key=os.getenv("BOCHA_API_KEY", ""),
        bocha_endpoint=os.getenv("BOCHA_ENDPOINT", "https://api.bochaai.com/v1/web-search"),
        feishu_webhooks=webhooks or DEFAULT_FEISHU_WEBHOOKS,
        jizhile_max_pages=int(os.getenv("OPINION_JIZHILE_MAX_PAGES", "1")),
        bocha_count=int(os.getenv("OPINION_BOCHA_COUNT", "10")),
    )

