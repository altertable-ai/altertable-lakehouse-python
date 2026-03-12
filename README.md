# Altertable Lakehouse Python SDK

You can use this SDK to query and ingest data in Altertable Lakehouse from Python applications.

## Install

```bash
pip install altertable-lakehouse
```

## Quick start

```python
from altertable_lakehouse import Client
from altertable_lakehouse.models import QueryRequest

client = Client(username="your_username", password="your_password")
metadata, rows = client.query(QueryRequest(statement="SELECT 1 AS ok"))
for row in rows:
    print(row)
```

## API reference

### Initialization

`Client(username: str | None = None, password: str | None = None, **options)`

Creates a client authenticated with Basic Auth credentials or token.

### Querying

`query(request: QueryRequest)` streams query rows.

`query_all(request: QueryRequest)` returns all rows in memory.

### Ingestion

`append(catalog: str, schema: str, table: str, data: dict | list[dict])` appends rows.

`upload(catalog: str, schema: str, table: str, format: UploadFormat, mode: UploadMode, content: bytes)` uploads a file payload.

### Query management

`get_query(query_id: str)` returns query status.

`cancel_query(query_id: str, session_id: str)` cancels a running query.

`validate(statement: str)` validates SQL without execution.

## Configuration

| Option | Type | Default | Description |
|---|---|---|---|
| `username` | `str \| None` | `None` | Basic Auth username (or `ALTERTABLE_USERNAME`). |
| `password` | `str \| None` | `None` | Basic Auth password (or `ALTERTABLE_PASSWORD`). |
| `basic_auth_token` | `str \| None` | `None` | Base64 `username:password` token (or env var). |
| `base_url` | `str` | `"https://api.altertable.ai"` | API base URL. |
| `timeout` | `int` | `10` | Request timeout in seconds. |

## Development

Prerequisites: Python 3.9+ and `pip`.

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## License

See [LICENSE](LICENSE).