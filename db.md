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
- `sources`: enabled data sources, currently `wechat`, `web`, `brave`, `tophub`, `toutiao`, or any combination.
- `enabled`: whether the plan is active.
- `created_at`: creation time.
- `updated_at`: last edit time.

### `items`

Stores normalized public opinion records collected from 极致了, 博查搜索, Brave,
TopHub, and 头条搜索.
Documents are deduplicated by `unique_key`, so repeated runs can safely process
the same source results.

Core fields:

- `unique_key`: stable dedupe key, such as `wechat:<url>`, `web:<url>`, `brave:<url>`, `tophub:<url>`, or `toutiao:<url>`.
- `source_type`: `wechat`, `web`, `brave`, `tophub`, or `toutiao`.
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
- `status`: `running`, `success`, `partial_success`, or `failed`.
- `started_at`: job start time.
- `ended_at`: job end time.
- `plan_count`: number of enabled plans read by collection jobs.
- `collected_count`: number of source items accepted by keyword filtering.
- `item_count`: number of related items included in a daily summary.
- `pushed_count`: number of Feishu messages sent.
- `errors`: list of classification, notification, or local configuration errors that make the run failed.
- `warnings`: list of source collection errors, such as third-party API timeouts. Runs with at least one successful source and only source warnings are marked `partial_success`.
- `request_results`: per-request source snapshots for troubleshooting. Each entry stores `plan_id`, `plan_name`, `source`, the query condition, request parameters or payload, and the raw response body. Failed requests store `error` when no response body is available.
