import os
import json
import base64
import ssl
import httpx
from typing import Any, Iterator, Optional, Union, Tuple, NoReturn
from .models import (
    AppendRequestSingle,
    AppendRequestBatch,
    AppendResponse,
    TaskResponse,
    QueryRequest,
    QueryLogResponse,
    CancelQueryResponse,
    ValidateRequest,
    ValidateResponse,
    AutocompleteRequest,
    AutocompleteResponse,
    UploadFormat,
    UploadMode,
    QueryMetadata,
    QueryResult,
)
from .errors import (
    AuthError,
    BadRequestError,
    NetworkError,
    TimeoutError,
    ParseError,
    ApiError,
    ConfigurationError,
    AltertableLakehouseError,
)


class Client:
    def __init__(
        self,
        base_url: str = "https://api.altertable.ai",
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 30.0,
        user_agent_suffix: Optional[str] = None,
        verify: Union[bool, ssl.SSLContext] = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        auth_token = None
        if token:
            auth_token = token
        elif username and password:
            auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()
        elif "ALTERTABLE_BASIC_AUTH_TOKEN" in os.environ:
            auth_token = os.environ["ALTERTABLE_BASIC_AUTH_TOKEN"]
        elif "ALTERTABLE_USERNAME" in os.environ and "ALTERTABLE_PASSWORD" in os.environ:
            u = os.environ["ALTERTABLE_USERNAME"]
            p = os.environ["ALTERTABLE_PASSWORD"]
            auth_token = base64.b64encode(f"{u}:{p}".encode()).decode()

        if not auth_token:
            raise ConfigurationError("No credentials provided.")

        ua = "altertable-lakehouse-python/0.1.0"
        if user_agent_suffix:
            ua += f" {user_agent_suffix}"

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=verify,
            headers={
                "Authorization": f"Basic {auth_token}",
                "User-Agent": ua,
            },
        )

    def _handle_error(self, e: Exception) -> NoReturn:
        if isinstance(e, httpx.TimeoutException):
            raise TimeoutError("Request timed out", e)
        if isinstance(e, httpx.RequestError):
            raise NetworkError(f"Network error: {str(e)}", e)
        raise AltertableLakehouseError(f"Unexpected error: {str(e)}", e)

    def _check_response(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        if response.status_code == 401:
            raise AuthError("Unauthorized", response.status_code)
        if response.status_code == 400:
            raise BadRequestError(response.text, response.status_code)
        raise ApiError(response.text, response.status_code)

    def append(
        self,
        catalog: str,
        schema: str,
        table: str,
        data: Union[AppendRequestSingle, AppendRequestBatch],
        sync: Optional[bool] = None,
    ) -> AppendResponse:
        try:
            payload = data.model_dump() if hasattr(data, "model_dump") else data
            params = {"catalog": catalog, "schema": schema, "table": table}
            if sync is not None:
                params["sync"] = "true" if sync else "false"
            res = self._client.post("/append", params=params, json=payload)
            self._check_response(res)
            return AppendResponse(**res.json())
        except httpx.RequestError as e:
            self._handle_error(e)

    def get_task(self, task_id: str) -> TaskResponse:
        try:
            res = self._client.get(f"/tasks/{task_id}")
            self._check_response(res)
            return TaskResponse(**res.json())
        except httpx.RequestError as e:
            self._handle_error(e)

    def upload(
        self,
        catalog: str,
        schema: str,
        table: str,
        format: UploadFormat,
        mode: UploadMode,
        content: bytes,
        primary_key: Optional[str] = None,
    ) -> None:
        params = {
            "catalog": catalog,
            "schema": schema,
            "table": table,
            "format": format.value,
            "mode": mode.value,
        }
        if primary_key:
            params["primary_key"] = primary_key
        try:
            res = self._client.post(
                "/upload",
                params=params,
                content=content,
                headers={"Content-Type": "application/octet-stream"},
            )
            self._check_response(res)
        except httpx.RequestError as e:
            self._handle_error(e)

    def get_query(self, query_id: str) -> QueryLogResponse:
        try:
            res = self._client.get(f"/query/{query_id}")
            self._check_response(res)
            return QueryLogResponse(**res.json())
        except httpx.RequestError as e:
            self._handle_error(e)

    def cancel_query(self, query_id: str, session_id: str) -> CancelQueryResponse:
        try:
            res = self._client.delete(f"/query/{query_id}", params={"session_id": session_id})
            self._check_response(res)
            return CancelQueryResponse(**res.json())
        except httpx.RequestError as e:
            self._handle_error(e)

    def validate(self, request: ValidateRequest) -> ValidateResponse:
        try:
            payload = request.model_dump(exclude_none=True, by_alias=True)
            res = self._client.post("/validate", json=payload)
            self._check_response(res)
            return ValidateResponse(**res.json())
        except httpx.RequestError as e:
            self._handle_error(e)

    def autocomplete(self, request: AutocompleteRequest) -> AutocompleteResponse:
        payload = request.model_dump(exclude_none=True, by_alias=True)
        try:
            res = self._client.post("/autocomplete", json=payload)
            self._check_response(res)
            return AutocompleteResponse(**res.json())
        except httpx.RequestError as e:
            self._handle_error(e)

    def query(self, request: QueryRequest) -> Tuple[QueryMetadata, list[Any], Iterator[Any]]:
        payload = request.model_dump(exclude_none=True, by_alias=True)
        res: Optional[httpx.Response] = None
        try:
            req = self._client.build_request(
                "POST",
                "/query",
                json=payload,
                headers={"Accept": "application/x-ndjson"},
            )
            res = self._client.send(req, stream=True)
            self._check_response(res)

            line_index = 0
            line_iter = res.iter_lines()

            def next_item() -> Optional[Any]:
                nonlocal line_index
                for line in line_iter:
                    if not line.strip():
                        continue
                    line_index += 1
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ParseError("Failed to parse NDJSON line", line_index, line) from exc
                return None

            first_item = next_item()
            if first_item is None:
                res.close()
                return QueryMetadata(), [], iter(())

            metadata = QueryMetadata(
                values=first_item if isinstance(first_item, dict) else {"value": first_item}
            )

            columns: list[Any] = []
            buffered_row: Optional[Any] = None
            second_item = next_item()
            if second_item is not None:
                if isinstance(second_item, list):
                    columns = second_item
                elif isinstance(second_item, dict) and isinstance(second_item.get("columns"), list):
                    columns = second_item["columns"]
                else:
                    buffered_row = second_item

            def row_iter() -> Iterator[Any]:
                try:
                    if buffered_row is not None:
                        yield buffered_row
                    while True:
                        item = next_item()
                        if item is None:
                            break
                        yield item
                finally:
                    res.close()

            return metadata, columns, row_iter()

        except httpx.RequestError as e:
            if res is not None:
                res.close()
            self._handle_error(e)
        except Exception:
            if res is not None:
                res.close()
            raise

    def query_all(self, request: QueryRequest) -> QueryResult:
        metadata, columns, iterator = self.query(request)
        rows = list(iterator)
        return QueryResult(metadata=metadata, columns=columns, rows=rows)
