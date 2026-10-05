import datetime
import json
from decimal import Decimal

import httpx
import pytest

ibis = pytest.importorskip("ibis")
pa = pytest.importorskip("pyarrow")
pd = pytest.importorskip("pandas")

from altertable_lakehouse import Client, errors  # noqa: E402
from altertable_lakehouse.ibis import Backend  # noqa: E402


@pytest.fixture
def connection():
    requests = []
    responses = []

    def handler(request):
        requests.append(request)
        columns, rows = responses.pop(0)
        body = [{"query_id": "query-id"}, columns, *rows]
        return httpx.Response(200, text="\n".join(json.dumps(item) for item in body))

    client = Client(token="test-token")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    backend = ibis.altertable.from_connection(
        client, catalog="warehouse", database="main"
    )
    yield backend, requests, responses
    client._client.close()


def test_entry_point_and_client_ownership(connection):
    backend, _, responses = connection
    responses.append((["n"], [[1]]))

    backend.disconnect()
    result = backend.sql("SELECT 1 AS n", schema={"n": "int32"}).execute()

    assert isinstance(backend, Backend)
    assert result.n.tolist() == [1]
    assert not backend.client._client.is_closed


def test_connect_owns_client_and_rejects_ambiguous_options():
    backend = ibis.altertable.connect(token="test-token")

    backend.disconnect()

    assert backend.client._client.is_closed
    with pytest.raises(ValueError, match="either client"):
        ibis.altertable.connect(client=backend.client, token="other")


@pytest.mark.parametrize("typed_columns", [False, True])
def test_result_shapes_and_request_contract(connection, typed_columns):
    backend, requests, responses = connection
    columns = [{"name": "n", "type": "INTEGER"}] if typed_columns else ["n"]
    responses.extend([(columns, [[1], [2]])] * 4 + [(columns, [[3]])] * 2)
    table = backend.sql("SELECT n FROM numbers", schema={"n": "int32"})

    frame = table.execute()
    series = table.n.execute()
    arrow_table = table.to_pyarrow()
    arrow_column = table.n.to_pyarrow()
    scalar = table.n.sum().execute()
    arrow_scalar = table.n.sum().to_pyarrow()

    assert isinstance(frame, pd.DataFrame)
    assert isinstance(series, pd.Series)
    assert frame.n.tolist() == series.tolist() == [1, 2]
    assert isinstance(arrow_table, pa.Table)
    assert isinstance(arrow_column, (pa.Array, pa.ChunkedArray))
    assert arrow_column.to_pylist() == [1, 2]
    assert scalar == arrow_scalar.as_py() == 3
    assert isinstance(arrow_scalar, pa.Scalar)
    payload = json.loads(requests[0].content)
    assert payload["catalog"] == "warehouse"
    assert payload["schema"] == "main"
    assert payload["statement"].startswith("SELECT")
    assert requests[0].headers["accept"] == "application/x-ndjson"


@pytest.mark.parametrize("rows", [[], [[None, None]]])
def test_empty_and_null_results_preserve_schema(connection, rows):
    backend, _, responses = connection
    responses.append((["n", "amount"], rows))
    table = backend.sql(
        "SELECT n, amount FROM numbers",
        schema={"n": "int64", "amount": "decimal(38,9)"},
    )

    result = table.to_pyarrow()

    assert result.num_rows == len(rows)
    assert result.schema.types == [pa.int64(), pa.decimal128(38, 9)]
    assert result.to_pylist() == ([{"n": None, "amount": None}] if rows else [])


def test_decimal_temporal_json_and_nested_conversion(connection):
    backend, requests, responses = connection
    amount = "12345678901234567890.123456789"
    schema = {
        "amount": "decimal(38,9)",
        "day": "date",
        "at": "timestamp(9)",
        "clock": "time",
        "payload": "json",
        "items": "array<int32>",
        "record": "struct<name: string, n: int32>",
    }
    rows = [
        [
            amount,
            "2026-01-01",
            "2026-01-01T01:02:03.123456789",
            "01:02:03.123456",
            {"ok": True},
            [1, None],
            ["one", 1],
        ]
    ]
    responses.append((list(schema), rows))
    table = backend.sql("SELECT * FROM records", schema=schema)

    result = table.to_pyarrow().to_pylist()[0]

    assert result["amount"] == Decimal(amount)
    assert result["day"] == datetime.date(2026, 1, 1)
    assert result["at"] == pd.Timestamp("2026-01-01T01:02:03.123456789")
    assert result["clock"] == datetime.time(1, 2, 3, 123456)
    assert json.loads(result["payload"]) == {"ok": True}
    assert result["items"] == [1, None]
    assert result["record"] == {"name": "one", "n": 1}
    assert 'CAST("t0"."amount" AS TEXT)' in json.loads(requests[0].content)["statement"]


def test_nullable_integers_preserve_precision_in_pandas(connection):
    backend, _, responses = connection
    number = 9007199254740993
    responses.append((["n", "items"], [[number, [number, None]], [None, None]]))
    table = backend.sql(
        "SELECT n, items FROM numbers", schema={"n": "int64", "items": "array<int64>"}
    )

    result = table.execute()

    assert result.n.iloc[0] == number
    assert result["items"].iloc[0] == [number, None]
    assert pd.isna(result.n.iloc[1])


def test_schema_discovery_quotes_identifiers_and_does_not_execute_data(connection):
    backend, requests, responses = connection
    responses.append((["column_name", "column_type", "null"], [["id", "BIGINT", "NO"]]))

    table = backend.table('odd " table', database=('cat"alog', "odd schema"))

    assert table.schema() == ibis.schema({"id": "!int64"})
    assert (
        json.loads(requests[0].content)["statement"]
        == 'DESCRIBE SELECT * FROM "cat""alog"."odd schema"."odd "" table"'
    )
    assert '"cat""alog"."odd schema"."odd "" table"' in backend.compile(table)


def test_sql_schema_is_described_without_executing_the_query(connection):
    backend, requests, responses = connection
    responses.append(
        (["column_name", "column_type", "null"], [["n", "INTEGER", "YES"]])
    )

    table = backend.sql("SELECT error('must not execute') AS n")

    assert table.schema() == ibis.schema({"n": "int32"})
    assert json.loads(requests[0].content)["statement"].startswith("DESCRIBE SELECT")


def test_discovery_filters_namespaces_and_like(connection):
    backend, requests, responses = connection
    responses.extend(
        [
            (["catalog_name"], [["warehouse"], ["other"]]),
            (["schema_name"], [["main"], ["staging"]]),
            (["table_name"], [["orders"], ["other"]]),
        ]
    )

    assert backend.list_catalogs(like="ware") == ["warehouse"]
    assert backend.list_databases(catalog="warehouse", like="main") == ["main"]
    assert backend.list_tables(
        database=("warehouse", "odd's schema"), like="orders"
    ) == ["orders"]
    statement = json.loads(requests[-1].content)["statement"]
    assert "table_catalog = 'warehouse'" in statement
    assert "table_schema = 'odd''s schema'" in statement


@pytest.mark.parametrize(
    "dtype",
    ["binary", "interval('D')", "map<string, int32>", "uuid", "array<decimal(38,9)>"],
)
def test_unsupported_types_fail_before_query(connection, dtype):
    backend, requests, _ = connection
    table = backend.sql("SELECT value FROM records", schema={"value": dtype})

    with pytest.raises(
        ibis.common.exceptions.UnsupportedOperationError, match="Cast it to string"
    ):
        table.execute()

    assert requests == []


def test_unsupported_operations_fail_before_query(connection):
    backend, requests, _ = connection

    @ibis.udf.scalar.python
    def identity(value: int) -> int:
        return value

    with pytest.raises(
        ibis.common.exceptions.UnsupportedOperationError, match="memtables"
    ):
        backend.execute(ibis.memtable({"n": [1]}))
    with pytest.raises(ibis.common.exceptions.UnsupportedOperationError, match="UDFs"):
        backend.execute(identity(1))
    with pytest.raises(NotImplementedError, match="mutations"):
        backend.create_table("new_table", schema={"n": "int32"})
    with pytest.raises(NotImplementedError, match="mutations"):
        backend.drop_table("existing")

    assert requests == []


def test_parameters_limits_and_batches(connection):
    backend, requests, responses = connection
    responses.append((["n"], [[2], [3]]))
    table = backend.sql("SELECT n FROM numbers", schema={"n": "int32"})
    minimum = ibis.param("int32")
    expr = table.filter(table.n > minimum)

    batches = list(expr.to_pyarrow_batches(params={minimum: 1}, limit=2, chunk_size=1))

    assert [batch.num_rows for batch in batches] == [1, 1]
    statement = json.loads(requests[0].content)["statement"]
    assert "LIMIT 2" in statement
    assert "> 1" in statement


@pytest.mark.parametrize("failure", ["authentication", "network", "stream"])
def test_transport_errors_keep_sdk_types(failure):
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "network":
            raise httpx.ConnectError("offline", request=request)
        if failure == "authentication":
            return httpx.Response(401)
        return httpx.Response(
            200, text='{}\n[{"name":"n","type":"INTEGER"}]\n{"error":"query failed"}\n'
        )

    client = Client(token="test-token")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    backend = ibis.altertable.from_connection(client)
    error = {
        "authentication": errors.AuthError,
        "network": errors.NetworkError,
        "stream": errors.QueryError,
    }[failure]

    with pytest.raises(error):
        backend.sql("SELECT 1 AS n", schema={"n": "int32"}).execute()

    client._client.close()
