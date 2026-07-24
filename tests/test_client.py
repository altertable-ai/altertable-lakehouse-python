# type: ignore
import os
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
    assert columns == ["1"]
    assert row_values == [[1]]

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
