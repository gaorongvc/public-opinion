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
- `FEISHU_WEBHOOKS`: comma-separated Feishu bot webhook URLs. Defaults to the existing global hooks.
- `MONGO_URI`: optional MongoDB URI fallback when `grlibs.mdb` is unavailable.
- `MONGO_DB`: MongoDB database name for `MONGO_URI`, default `opinion`.

MongoDB collections:

The default database is `db3.opinion` when `grlibs.mdb` is available. If
`MONGO_URI` is configured directly, the database name is `MONGO_DB`, defaulting
to `opinion`.

### `plans`

Stores monitoring plans edited in the admin UI. Only documents with
`enabled: true` are read by `collect_and_notify_once`.

Core fields:

- `name`: plan name shown in the UI.
- `kw`: required keywords. All tokens must be present.
- `any_kw`: optional keywords. At least one token must be present when set.
- `ex_kw`: exclusion keywords. Any hit filters the item out.
- `sources`: enabled data sources, currently `wechat`, `web`, `brave`, `tophub`, or any combination.
- `enabled`: whether the plan is active.
- `created_at`: creation time.
- `updated_at`: last edit time.

### `items`

Stores normalized public opinion records collected from 极致了, 博查搜索, Brave,
and TopHub.
Documents are deduplicated by `unique_key`, so repeated runs can safely process
the same source results.

Core fields:

- `unique_key`: stable dedupe key, such as `wechat:<url>`, `web:<url>`, `brave:<url>`, or `tophub:<url>`.
- `source_type`: `wechat`, `web`, `brave`, or `tophub`.
- `source_name`: WeChat account name, website name, hot-list source name, or source display name.
- `title`: article or page title.
- `url`: original content URL.
- `content`: full text when available, otherwise source summary/snippet.
- `summary`: short source summary used for display and classification.
- `published_at`: source publish time when available.
- `metrics`: source-specific counters, such as WeChat read count.
- `raw`: original API response payload for debugging.
- `matched_plan_ids`: plan ids that matched this item.
- `matched_plan_names`: plan names that matched this item when first inserted.
- `related`: LLM relevance result.
- `sentiment`: `positive`, `neutral`, or `negative`.
- `reason`: short Chinese explanation used in Feishu messages.
- `notified_at`: set after successful instant Feishu push.
- `created_at`: first collection time.
- `updated_at`: last update time.

Indexes are created at runtime for `unique_key`, `created_at`, and `related`.

### `runs`

Stores Airflow-callable job execution records for observability and the admin
UI task page.

Core fields:

- `job`: `collect_and_notify_once` or `daily_summary`.
- `status`: `running`, `success`, or `failed`.
- `started_at`: job start time.
- `ended_at`: job end time.
- `plan_count`: number of enabled plans read by collection jobs.
- `collected_count`: number of source items accepted by keyword filtering.
- `item_count`: number of related items included in a daily summary.
- `pushed_count`: number of Feishu messages sent.
- `errors`: list of source, classification, or notification errors.

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
