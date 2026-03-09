# Altertable Lakehouse Python SDK

Official Python SDK for the Altertable Lakehouse API.

## Installation

```bash
pip install altertable-lakehouse
```

## Usage

### Initialization

```python
from altertable_lakehouse import Client

client = Client(username="your_username", password="your_password")
```

### Querying

```python
from altertable_lakehouse.models import QueryRequest

# Stream rows (good for large datasets)
req = QueryRequest(statement="SELECT * FROM my_table")
metadata, row_iterator = client.query(req)
for row in row_iterator:
    print(row)

# Accumulate all rows in memory
result = client.query_all(req)
print(result.rows)
```

### Append

```python
res = client.append(catalog="my_cat", schema="my_schema", table="my_table", data={"col1": "val1"})
print(res.ok)
```

### Upload

```python
from altertable_lakehouse.models import UploadFormat, UploadMode

with open("data.csv", "rb") as f:
    client.upload(
        catalog="my_cat", 
        schema="my_schema", 
        table="my_table", 
        format=UploadFormat.CSV, 
        mode=UploadMode.APPEND, 
        content=f.read()
    )
```

### Validate Query

```python
res = client.validate("SELECT * FROM non_existent")
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
