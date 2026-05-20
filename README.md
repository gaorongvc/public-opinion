# public-opinion

## Opinion platform

Install dependencies with uv:

```bash
uv sync
```

Environment variables:

Create a `.env` file before running jobs, source smoke tests, or the admin UI.

- `JZL_API_KEY`: 极致了 API key. Defaults to the existing project key.
- `BOCHA_API_KEY`: 博查搜索 API key.
- `BRAVE_API_KEY`: Brave Search API key.
- `TOPHUB_TOKEN`: TopHub Data API token.
- `JINA_API_KEY`: Jina Reader API key used for 头条搜索.
- `FEISHU_WEBHOOKS`: comma-separated Feishu bot webhook URLs. Defaults to the existing global hooks.

Run the admin UI:

```bash
uv run python -m uvicorn opinion.web:app --host 0.0.0.0 --port 8009
```

Airflow can call either Python callable directly:

```python
from opinion.jobs.collect_and_notify_once import run as collect_and_notify_once
from opinion.jobs.daily_summary import run as daily_summary
```

Or use CLI-style commands:

```bash
uv run python -m opinion.jobs.collect_and_notify_once
uv run python -m opinion.jobs.daily_summary
```

Run tests:

```bash
uv run python -m pytest
```

# 注意
1. brave web/news search 拿不到当日数据，舆情场景数据的及时性不够；
2. bocha ai/web search 无法实现 kw, any_kw 及 ex_kw 这样的逻辑，通搜结果较差；
