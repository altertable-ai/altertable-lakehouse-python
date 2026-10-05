import json
from typing import Iterator

import httpx
import pytest

from altertable_lakehouse import Client, errors, models


def test_query_parquet_preserves_request_context_and_returns_bytes() -> None:
    requests: list[httpx.Request] = []
    payload = b"parquet payload"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, content=payload, headers={"Content-Type": "application/parquet"}
        )

    client = Client(token="test-token")
    client._client.close()
    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as transport:
        client._client = transport
        request = models.QueryRequest(
            statement="SELECT 1", catalog="warehouse", schema="main"
        )

        result = client.query_parquet(request)

        assert result == payload
        assert json.loads(requests[0].content) == {
            "statement": "SELECT 1",
            "catalog": "warehouse",
            "schema": "main",
            "format": "parquet",
        }
        assert requests[0].headers["accept"] == "application/parquet"


@pytest.mark.parametrize(
    "status, content_type, expected",
    [
        (401, "text/plain", errors.AuthError),
        (400, "text/plain", errors.BadRequestError),
        (200, "application/x-ndjson", errors.ApiError),
    ],
)
def test_query_parquet_rejects_http_errors_and_wrong_format(
    status: int, content_type: str, expected: type[errors.ApiError]
) -> None:
    response = httpx.Response(status, headers={"Content-Type": content_type})
    client = Client(token="test-token")
    client._client.close()
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(lambda _: response),
    ) as transport:
        client._client = transport

        with pytest.raises(expected):
            client.query_parquet(models.QueryRequest(statement="SELECT 1"))

        assert response.is_closed


@pytest.mark.parametrize(
    "cause, expected",
    [(httpx.ReadError, errors.NetworkError), (httpx.ReadTimeout, errors.TimeoutError)],
)
def test_query_parquet_closes_interrupted_response(
    cause: type[httpx.RequestError], expected: type[errors.AltertableLakehouseError]
) -> None:
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            yield b"PAR1"
            raise cause("stream interrupted")

    response = httpx.Response(
        200, stream=BrokenStream(), headers={"Content-Type": "application/parquet"}
    )
    client = Client(token="test-token")
    client._client.close()
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(lambda _: response),
    ) as transport:
        client._client = transport

        with pytest.raises(expected):
            client.query_parquet(models.QueryRequest(statement="SELECT 1"))

        assert response.is_closed
