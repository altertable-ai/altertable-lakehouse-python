# type: ignore
import os
import json
import ssl
from io import BytesIO
import pytest
import httpx
from testcontainers.core.container import DockerContainer
from altertable_lakehouse import Client, models, errors

@pytest.fixture(scope="module", autouse=True)
def mock_server():
    if "CI" in os.environ:
        yield
        return
    
    container = DockerContainer("ghcr.io/altertable-ai/altertable-mock:latest")
    container.with_env("ALTERTABLE_MOCK_USERS", "testuser:testpass")
    container.with_exposed_ports(15000)
    container.start()
    
    port = container.get_exposed_port(15000)
    host = container.get_container_host_ip()
    os.environ["ALTERTABLE_MOCK_PORT"] = str(port)
    os.environ["ALTERTABLE_MOCK_HOST"] = host
    
    yield container
    
    container.stop()

@pytest.fixture
def base_url():
    if "CI" in os.environ:
        return "http://localhost:15000"
    port = os.environ.get("ALTERTABLE_MOCK_PORT", "15000")
    host = os.environ.get("ALTERTABLE_MOCK_HOST", "localhost")
    return f"http://{host}:{port}"

@pytest.fixture
def client(base_url):
    return Client(base_url=base_url, username="testuser", password="testpass")

def test_query_all(client):
    req = models.QueryRequest(statement="SELECT 1 as num")
    res = client.query_all(req)
    assert "statement" in res.metadata.values
    assert isinstance(res.columns, list)
    assert isinstance(res.rows, list)


def test_query_request_serializes_named_and_positional_bind_values():
    named = models.QueryRequest(statement="SELECT $min_age", params={"min_age": 25})
    positional = models.QueryRequest(statement="SELECT $1", params=[25])

    assert named.model_dump(exclude_none=True)["params"] == {"min_age": 25}
    assert positional.model_dump(exclude_none=True)["params"] == [25]

def test_upsert_sends_primary_key_without_unsupported_mode(client):
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        return httpx.Response(204, request=request)

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    client.upsert(
        catalog="cat",
        schema="sch",
        table="tbl",
        primary_key="id",
        content=b'{"id":1}',
    )

    assert captured["params"] == {
        "catalog": "cat",
        "schema": "sch",
        "table": "tbl",
        "primary_key": "id",
    }
    assert "mode" not in captured["params"]


def test_upsert_forwards_cursor_field_and_content_type(client):
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        captured["content_type"] = request.headers.get("content-type")
        return httpx.Response(204, request=request)

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    client.upsert(
        catalog="cat",
        schema="sch",
        table="tbl",
        primary_key="account_id,event_id",
        cursor_field="updated_at,sequence",
        content=b'[{"account_id":1}]',
        content_type="application/json",
    )

    assert captured["params"]["cursor_field"] == "updated_at,sequence"
    assert captured["content_type"] == "application/json"


def test_upsert_requires_primary_key(client):
    with pytest.raises(TypeError, match="primary_key"):
        client.upsert(catalog="cat", schema="sch", table="tbl", content=b'{"id":1}')


def test_upload_sends_required_parameters_and_content_type(client):
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        captured["content_type"] = request.headers.get("content-type")
        captured["content"] = request.content
        return httpx.Response(200, request=request)

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    client.upload(
        catalog="cat",
        schema="sch",
        table="tbl",
        mode=models.UploadMode.CREATE,
        content=BytesIO(b"id,name\n1,Alice\n"),
        content_type="text/csv",
    )

    assert captured["params"] == {
        "catalog": "cat",
        "schema": "sch",
        "table": "tbl",
        "mode": "create",
    }
    assert captured["content_type"] == "text/csv"
    assert captured["content"] == b"id,name\n1,Alice\n"


def test_upload_supports_create_append(client):
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, request=request)

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    client.upload(
        catalog="cat",
        schema="sch",
        table="tbl",
        mode=models.UploadMode.CREATE_APPEND,
        content=b"id,name\n1,Alice\n",
    )

    assert captured["params"]["mode"] == "create_append"


def test_upload_omits_content_type_and_surfaces_api_errors(client):
    captured = {}

    def handler(request):
        captured["content_type"] = request.headers.get("content-type")
        return httpx.Response(400, text="invalid upload", request=request)

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(errors.BadRequestError, match="invalid upload"):
        client.upload(
            catalog="cat",
            schema="sch",
            table="tbl",
            mode=models.UploadMode.APPEND,
            content=b'{"id":1}',
        )

    assert captured["content_type"] is None


def test_append(client):
    try:
        client.append(catalog="cat", schema="sch", table="tbl", data={"a": 1}, sync=False)
    except errors.BadRequestError:
        pass

def test_validate(client):
    res = client.validate(models.ValidateRequest(statement="SELECT 1"))
    assert res.valid is not None


def test_autocomplete(client):
    res = client.autocomplete(models.AutocompleteRequest(statement="SEL", max_suggestions=5))
    assert res.statement == "SEL"
    assert len(res.suggestions) <= 5
    assert any(suggestion.suggestion for suggestion in res.suggestions)


def test_get_query(client):
    try:
        client.get_query("00000000-0000-0000-0000-000000000000")
    except errors.ApiError as e:
        assert e.status_code == 404

def test_get_task(client):
    try:
        client.get_task("00000000-0000-0000-0000-000000000000")
    except errors.ApiError as e:
        assert e.status_code == 404

def test_cancel_query(client):
    try:
        client.cancel_query("00000000-0000-0000-0000-000000000000", "session-id")
    except errors.ApiError as e:
        assert e.status_code == 404

def test_query_returns_stream_metadata_and_columns(client):
    metadata, columns, rows = client.query(models.QueryRequest(statement="SELECT 1"))
    row_values = list(rows)

    assert metadata.values["statement"] == "SELECT 1"
    assert metadata.values["query_id"]
    assert columns == [{"name": "1", "type": "INTEGER"}]
    assert row_values == [[1]]


def test_query_forwards_v013_options_and_rejects_auto_with_session(client):
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            text='{"query_id":"query"}\n[]\n',
            headers={"content-type": "application/x-ndjson"},
            request=request,
        )

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    metadata, columns, rows = client.query(
        models.QueryRequest(
            statement="SELECT 1",
            compute_size=models.ComputeSize.XXL,
            dialect="postgres",
            format=models.QueryFormat.JSONL,
        )
    )

    assert metadata.values["query_id"] == "query"
    assert columns == []
    assert list(rows) == []
    assert captured["payload"] == {
        "statement": "SELECT 1",
        "compute_size": "2XL",
        "dialect": "postgres",
        "format": "jsonl",
    }

    with pytest.raises(errors.ConfigurationError, match="AUTO"):
        client.query(
            models.QueryRequest(
                statement="SELECT 1",
                compute_size=models.ComputeSize.AUTO,
                session_id="existing-session",
            )
        )


def test_query_raises_typed_error_from_ndjson_stream(client):
    def handler(request):
        return httpx.Response(
            200,
            text='{"query_id":"query"}\n[{"name":"id","type":"INTEGER"}]\n{"error":"worker failed"}\n',
            headers={"content-type": "application/x-ndjson"},
            request=request,
        )

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    _, _, rows = client.query(models.QueryRequest(statement="SELECT 1"))

    with pytest.raises(errors.QueryError, match="worker failed") as exc_info:
        list(rows)

    assert exc_info.value.line_index == 3
    assert exc_info.value.raw_content == '{"error": "worker failed"}'


def test_query_raises_typed_error_before_columns(client):
    def handler(request):
        return httpx.Response(
            200,
            text='{"query_id":"query"}\n{"error":"schema failed"}\n',
            headers={"content-type": "application/x-ndjson"},
            request=request,
        )

    client._client = httpx.Client(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(errors.QueryError, match="schema failed") as exc_info:
        client.query(models.QueryRequest(statement="SELECT 1"))

    assert exc_info.value.line_index == 2

def test_client_forwards_verify_false(monkeypatch, base_url):
    captured = {}

    class DummyHttpxClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(httpx, "Client", DummyHttpxClient)

    Client(base_url=base_url, username="testuser", password="testpass", verify=False)

    assert captured["verify"] is False

def test_client_forwards_ssl_context(monkeypatch, base_url):
    captured = {}
    ssl_context = ssl.create_default_context()

    class DummyHttpxClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(httpx, "Client", DummyHttpxClient)

    Client(
        base_url=base_url,
        username="testuser",
        password="testpass",
        verify=ssl_context,
    )

    assert captured["verify"] is ssl_context


def test_ibis_remote_query_shapes_and_precision(client):
    ibis = pytest.importorskip("ibis")
    from decimal import Decimal
    import pyarrow as pa
    import pandas as pd

    backend = ibis.altertable.from_connection(client, catalog="memory", database="main")
    amount = "12345678901234567890.123456789"
    table = backend.sql(
        f"SELECT n::INTEGER AS n, '{amount}'::DECIMAL(38,9) AS amount "
        "FROM range(1, 4) AS numbers(n)"
    )

    frame = table.execute()
    series = table.n.execute()
    column = table.n.to_pyarrow()
    scalar = table.amount.max().to_pyarrow()
    batches = list(table.to_pyarrow_batches(chunk_size=2))

    assert isinstance(frame, pd.DataFrame)
    assert frame.n.tolist() == [1, 2, 3]
    assert series.tolist() == [1, 2, 3]
    assert frame.amount.tolist() == [Decimal(amount)] * 3
    assert isinstance(column, (pa.Array, pa.ChunkedArray))
    assert column.to_pylist() == [1, 2, 3]
    assert scalar.as_py() == Decimal(amount)
    assert [batch.num_rows for batch in batches] == [2, 1]
    assert table.n.sum().execute() == 6
    assert table.filter(table.n < 0).to_pyarrow().schema == table.schema().to_pyarrow()
    assert table.filter(table.n < 0).execute().empty


def test_ibis_remote_schema_and_quoted_namespace(client):
    ibis = pytest.importorskip("ibis")
    import pandas as pd
    backend = ibis.altertable.from_connection(client, catalog="memory", database="main")
    client.query_all(models.QueryRequest(statement='CREATE SCHEMA "ibis schema"'))
    client.query_all(models.QueryRequest(statement='CREATE TABLE "ibis schema"."odd table" (id INTEGER NOT NULL, label VARCHAR)'))
    try:
        client.query_all(models.QueryRequest(statement='INSERT INTO "ibis schema"."odd table" VALUES (1, \'one\'), (2, NULL)'))

        table = backend.table("odd table", database=("memory", "ibis schema"))

        assert table.schema() == ibis.schema({"id": "!int32", "label": "string"})
        labels = table.order_by("id").execute().label
        assert labels.iloc[0] == "one"
        assert pd.isna(labels.iloc[1])
        assert "memory" in backend.list_catalogs()
        assert "ibis schema" in backend.list_databases(catalog="memory")
        assert backend.list_tables(database=("memory", "ibis schema")) == ["odd table"]
    finally:
        client.query_all(models.QueryRequest(statement='DROP TABLE "ibis schema"."odd table"'))
        client.query_all(models.QueryRequest(statement='DROP SCHEMA "ibis schema"'))


def test_ibis_remote_join_aggregate_window_and_parameters(client):
    ibis = pytest.importorskip("ibis")
    backend = ibis.altertable.from_connection(client)
    orders = backend.sql("SELECT * FROM (VALUES (1, 10), (1, 20), (2, 5)) AS orders(customer, amount)")
    customers = backend.sql("SELECT * FROM (VALUES (1, 'one'), (2, 'two')) AS customers(id, name)")
    minimum = ibis.param("int32")
    totals = orders.join(customers, orders.customer == customers.id).group_by("name").aggregate(total=orders.amount.sum())
    ranked = totals.mutate(position=ibis.row_number().over(order_by=totals.total.desc()))

    result = ranked.filter(ranked.total > minimum).order_by("position").execute(params={minimum: 0}, limit=2)

    assert result.name.tolist() == ["one", "two"]
    assert result.total.tolist() == [30, 5]
    assert result.position.tolist() == [0, 1]


def test_ibis_remote_arrow_types(client):
    ibis = pytest.importorskip("ibis")
    import datetime
    import json
    from decimal import Decimal
    import pandas as pd

    backend = ibis.altertable.from_connection(client)
    table = backend.sql(
        "SELECT DATE '2026-01-01' AS day, TIMESTAMPTZ '2026-01-01 01:02:03+00' AS moment, "
        "[1, NULL]::INTEGER[] AS items, {'name': 'one', 'n': 1} AS record, NULL::INTEGER AS missing, "
        "['12345678901234567890.123456789'::DECIMAL(38,9), NULL] AS amounts, "
        "TIMESTAMP_NS '2026-01-01 01:02:03.123456789' AS precise, "
        "JSON '{\"ok\":true}' AS payload, TIME '01:02:03.123456' AS clock, "
        "'\\x00\\xFF'::BLOB AS raw, MAP {'k': 1} AS mapping"
    )

    result = table.to_pyarrow().to_pylist()[0]

    assert result["day"] == datetime.date(2026, 1, 1)
    assert result["moment"] == pd.Timestamp("2026-01-01T01:02:03+00:00")
    assert result["items"] == [1, None]
    assert result["record"] == {"name": "one", "n": 1}
    assert result["missing"] is None
    assert result["amounts"] == [Decimal("12345678901234567890.123456789"), None]
    assert result["precise"] == pd.Timestamp("2026-01-01 01:02:03.123456789")
    assert json.loads(result["payload"]) == {"ok": True}
    assert result["clock"] == datetime.time(1, 2, 3, 123456)
    assert result["raw"] == b"\x00\xff"
    assert result["mapping"] == [("k", 1)]


def test_ibis_remote_nullable_integers_keep_precision(client):
    ibis = pytest.importorskip("ibis")
    import pandas as pd

    backend = ibis.altertable.from_connection(client)
    number = 9007199254740993
    table = backend.sql(
        f"SELECT * FROM (VALUES ({number}::BIGINT, [{number}::BIGINT, NULL]), "
        "(NULL, NULL)) AS numbers(n, items)"
    )

    result = table.execute()

    assert result.n.iloc[0] == number
    assert result["items"].iloc[0] == [number, None]
    assert pd.isna(result.n.iloc[1])


def test_ibis_describe_does_not_execute_data_and_preserves_query_errors(client):
    ibis = pytest.importorskip("ibis")
    backend = ibis.altertable.from_connection(client)

    table = backend.sql("SELECT error('ibis execution failed') AS value")

    with pytest.raises(errors.ApiError, match="ibis execution failed"):
        table.execute()
