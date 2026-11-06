import httpx
import pytest

from altertable_lakehouse import Client, errors, models


def test_successful_query_stays_lazy_with_split_lines_and_utf8():
    class GatedStream(httpx.SyncByteStream):
        released = False

        def __iter__(self):
            yield b'{}\n[{"name":"name","type":"VARCHAR"}]\n["Zo\xc3'
            yield b'\xab"]\n'
            assert self.released, "query read past the first available row"
            yield b'["last"]'

    stream = GatedStream()
    response = httpx.Response(200, stream=stream)
    client = Client(token="test-token")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(lambda _: response)
    )
    try:
        _, _, rows = client.query(models.QueryRequest(statement="SELECT name"))
        assert next(rows) == ["Zoë"]
        stream.released = True
        assert list(rows) == [["last"]]
        assert response.is_closed
    finally:
        client._client.close()


@pytest.mark.parametrize(
    "status, expected",
    [(400, errors.BadRequestError), (401, errors.AuthError), (503, errors.ApiError)],
)
def test_stream_http_errors_keep_sdk_types_body_and_close_response(status, expected):
    class ErrorBody(httpx.SyncByteStream):
        def __iter__(self):
            yield b"query "
            yield b"rejected"

    response = httpx.Response(status, stream=ErrorBody())
    client = Client(token="test-token")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(lambda _: response)
    )
    try:
        with pytest.raises(expected) as error:
            client.query(models.QueryRequest(statement="SELECT 1"))
        if status != 401:
            assert "query rejected" in str(error.value)
        assert response.is_closed
    finally:
        client._client.close()


@pytest.mark.parametrize(
    "prefix, line_index", [([], 2), (["[]"], 3), (["[]", "[1]"], 4)]
)
def test_stream_query_error_closes_response(prefix, line_index):
    body = "\n".join(["{}", *prefix, '{"error":"execution failed"}'])
    response = httpx.Response(200, stream=httpx.ByteStream(body.encode()))
    client = Client(token="test-token")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(lambda _: response)
    )

    with pytest.raises(errors.QueryError, match="execution failed") as error:
        client.query_all(models.QueryRequest(statement="SELECT 1"))

    assert error.value.line_index == line_index
    assert response.is_closed
    client._client.close()


@pytest.mark.parametrize(
    "cause, expected",
    [(httpx.ReadError, errors.NetworkError), (httpx.ReadTimeout, errors.TimeoutError)],
)
def test_stream_transport_errors_keep_sdk_types_and_close_response(cause, expected):
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{}\n["n"]\n[1]\n'
            raise cause("stream interrupted")

    response = httpx.Response(200, stream=BrokenStream())
    client = Client(token="test-token")
    client._client.close()
    client._client = httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(lambda _: response)
    )

    with pytest.raises(expected):
        client.query_all(models.QueryRequest(statement="SELECT 1"))

    assert response.is_closed
    client._client.close()
