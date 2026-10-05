import json
from typing import Any, Iterator

import httpx
import pytest

ibis = pytest.importorskip("ibis")

from altertable_lakehouse import Client, models  # noqa: E402
from altertable_lakehouse.ibis import Backend  # noqa: E402


@pytest.fixture
def connection() -> Iterator[tuple[Backend, list[httpx.Request], list[Any]]]:
    requests: list[httpx.Request] = []
    responses: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
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


def test_disconnect_preserves_borrowed_client(connection: Any) -> None:
    backend, _, responses = connection
    responses.append((["n"], [[1]]))

    backend.disconnect()
    result = backend.client.query_all(models.QueryRequest(statement="SELECT 1 AS n"))

    assert isinstance(backend, Backend)
    assert result.rows == [[1]]
    assert not backend.client._client.is_closed


def test_disconnect_closes_owned_client() -> None:
    backend = ibis.altertable.connect(token="test-token")

    backend.disconnect()

    assert backend.client._client.is_closed


def test_connection_options_cannot_override_borrowed_client(connection: Any) -> None:
    backend, _, _ = connection

    with pytest.raises(ValueError, match="either client"):
        ibis.altertable.connect(client=backend.client, token="other")


def test_schema_discovery_preserves_quoted_names_and_query_context(
    connection: Any,
) -> None:
    backend, requests, responses = connection
    responses.append((["column_name", "column_type", "null"], [["id", "BIGINT", "NO"]]))

    table = backend.table('odd " table', database=('cat"alog', "odd schema"))
    payload = json.loads(requests[0].content)

    assert table.schema() == ibis.schema({"id": "!int64"})
    assert (
        payload["statement"]
        == 'DESCRIBE SELECT * FROM "cat""alog"."odd schema"."odd "" table"'
    )
    assert payload["catalog"] == "warehouse"
    assert payload["schema"] == "main"


def test_unsupported_operations_fail_before_query(connection: Any) -> None:
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

    assert requests == []
