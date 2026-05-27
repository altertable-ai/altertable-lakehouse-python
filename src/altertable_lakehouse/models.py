from typing import Any, Dict, List, Optional, Literal, Union
from enum import Enum
from pydantic import BaseModel, Field


class ComputeSize(str, Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class UploadFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"


class UploadMode(str, Enum):
    CREATE = "create"
    APPEND = "append"
    UPSERT = "upsert"
    OVERWRITE = "overwrite"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class SessionKind(str, Enum):
    ARROW_FLIGHT_SQL = "ArrowFlightSQL"
    HTTP_QUERY = "HttpQuery"
    HTTP_CANCEL = "HttpCancel"
    HTTP_VALIDATE = "HttpValidate"
    HTTP_EXPLAIN = "HttpExplain"
    HTTP_AUTOCOMPLETE = "HttpAutocomplete"
    POSTGRES = "Postgres"


AppendRequestSingle = Dict[str, Any]
AppendRequestBatch = List[Dict[str, Any]]
AppendRequest = Union[AppendRequestSingle, AppendRequestBatch]


class AppendResponse(BaseModel):
    ok: bool
    error_code: Optional[Literal["invalid-data", "incompatible-schema"]] = None
    error_message: Optional[str] = None
    task_id: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus


class QueryRequest(BaseModel):
    statement: str
    catalog: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    session_id: Optional[str] = None
    compute_size: Optional[ComputeSize] = None
    sanitize: Optional[bool] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    timezone: Optional[str] = None
    ephemeral: Optional[bool] = None
    visible: Optional[bool] = None
    requested_by: Optional[str] = None
    query_id: Optional[str] = None
    cache: Optional[bool] = None


class QueryLogResponse(BaseModel):
    uuid: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    query: str
    session_id: Optional[str] = None
    client_interface: SessionKind
    error: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)
    progress: Optional[Dict[str, Any]] = None
    visible: bool
    requested_by: Optional[str] = None
    user_agent: Optional[str] = None


class CancelQueryResponse(BaseModel):
    cancelled: bool
    message: str


class ValidateRequest(BaseModel):
    statement: str
    catalog: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    session_id: Optional[str] = None


class ValidateResponse(BaseModel):
    valid: bool
    statement: str
    connections_errors: Any
    error: Optional[str] = None


class AutocompleteRequest(BaseModel):
    statement: str
    catalog: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    session_id: Optional[str] = None
    max_suggestions: Optional[int] = None


class AutocompleteSuggestion(BaseModel):
    suggestion: str
    suggestion_start: int
    suggestion_type: str
    suggestion_score: int
    extra_char: Optional[str] = None


class AutocompleteResponse(BaseModel):
    suggestions: List[AutocompleteSuggestion]
    statement: str
    connections_errors: Dict[str, Any]


class QueryMetadata(BaseModel):
    values: Dict[str, Any] = Field(default_factory=dict)


class QueryResult(BaseModel):
    metadata: QueryMetadata
    columns: List[Any] = Field(default_factory=list)
    rows: List[Any]
