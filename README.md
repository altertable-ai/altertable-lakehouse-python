# Altertable Lakehouse Python SDK

Official Python SDK for the Altertable Lakehouse API.

## Installation

```bash
pip install altertable-lakehouse
```

### Ibis (Python 3.10 or newer)

Requires Ibis 12. The base SDK still supports Python 3.9.

```bash
pip install 'altertable-lakehouse[ibis]'
```

Ibis compiles DuckDB SQL; the SDK executes it remotely over HTTP. No local
DuckDB installation is needed.

```python
import ibis

con = ibis.altertable.connect(
    username="your_username",
    password="your_password",
    catalog="my_catalog",
    database="my_schema",
)

orders = con.table("orders")
totals = orders.group_by("customer_id").aggregate(total=orders.amount.sum())
print(totals.execute())     # pandas DataFrame
print(totals.to_pyarrow())  # Arrow table
con.disconnect()
```

`database` means an Altertable schema. Use
`con.table("orders", database=("catalog", "schema"))` for a qualified table.
Discover data with `list_catalogs()`, `list_databases()`, and `list_tables()`.

Reuse an existing SDK client with:

```python
con = ibis.altertable.from_connection(client, catalog="my_catalog", database="my_schema")
```

`connect()` accepts the SDK's credentials, environment variables, `base_url`,
`timeout`, and `verify` options. `disconnect()` closes only clients it created.
See the [runnable example](examples/ibis_queries.py) for SQL expressions,
parameters, compilation, and Arrow output.

Limitations:

* Results are buffered in memory, including `to_pyarrow_batches()`.
* Nested decimals, binary, map, interval, UUID, and geospatial results require
  an explicit cast to string. Top-level decimals retain their precision.
* Memtables, UDFs, table/view mutations, and raw SQL cursors are unsupported.
  Use the SDK's query/upload methods for writes.
* URL-based `ibis.connect()` is unsupported. Use the connection methods above.

## Usage

### Initialization

```python
from altertable_lakehouse import Client

client = Client(username="your_username", password="your_password")

# Disable TLS certificate verification for development only
client = Client(username="your_username", password="your_password", verify=False)
```

### Querying

```python
from altertable_lakehouse.models import QueryRequest

# Stream rows (good for large datasets)
req = QueryRequest(statement="SELECT * FROM my_table")
metadata, columns, row_iterator = client.query(req)
print(metadata.values)
print(columns)
for row in row_iterator:
    print(row)

# Accumulate all rows in memory
result = client.query_all(req)
print(result.metadata.values)
print(result.columns)
print(result.rows)
```

### Append

```python
res = client.append(
    catalog="my_cat",
    schema="my_schema",
    table="my_table",
    data={"col1": "val1"},
    sync=False,
)
print(res.ok)

if res.task_id:
    task = client.get_task(res.task_id)
    print(task.status)
```

### Upsert

```python
with open("data.csv", "rb") as f:
    client.upsert(
        catalog="my_cat",
        schema="my_schema",
        table="my_table",
        primary_key="id",
        content=f.read(),
    )
```

### Upload

```python
from altertable_lakehouse.models import UploadMode

with open("data.csv", "rb") as f:
    client.upload(
        catalog="my_cat",
        schema="my_schema",
        table="my_table",
        mode=UploadMode.CREATE,
        content=f,
        content_type="text/csv",
    )
```

### Validate Query

```python
from altertable_lakehouse.models import ValidateRequest

res = client.validate(ValidateRequest(statement="SELECT * FROM non_existent"))
print(res.valid)
print(res.connections_errors)
```

### Query Log & Cancellation

```python
# Get query status
log_res = client.get_query("query_uuid_here")
print(log_res.progress)

# Cancel a query
cancel_res = client.cancel_query("query_uuid_here", "session_id_here")
print(cancel_res.cancelled)
```

### Autocomplete

```python
from altertable_lakehouse.models import AutocompleteRequest

res = client.autocomplete(AutocompleteRequest(statement="SEL", max_suggestions=5))
print(res.statement)
print([suggestion.suggestion for suggestion in res.suggestions])
```
