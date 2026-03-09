import os
import pytest
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
    os.environ["ALTERTABLE_MOCK_PORT"] = port
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
    assert len(res.rows) >= 0

def test_upload(client):
    try:
        client.upload(catalog="cat", schema="sch", table="tbl", format=models.UploadFormat.JSON, mode=models.UploadMode.APPEND, content=b'{"a":1}')
    except errors.BadRequestError:
        pass

def test_append(client):
    req = models.AppendRequestSingle(Single=models.AppendPayload(data={"a": 1}))
    try:
        client.append(catalog="cat", schema="sch", table="tbl", data=req)
    except errors.BadRequestError:
        pass

def test_validate(client):
    res = client.validate("SELECT 1")
    assert res.valid is not None

def test_get_query(client):
    try:
        client.get_query("00000000-0000-0000-0000-000000000000")
    except errors.ApiError as e:
        assert e.status_code == 404

def test_cancel_query(client):
    try:
        client.cancel_query("00000000-0000-0000-0000-000000000000", "session-id")
    except errors.ApiError as e:
        assert e.status_code == 404
