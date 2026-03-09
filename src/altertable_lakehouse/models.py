from typing import Any, Dict, List, Optional, Literal, Union
from enum import Enum
from pydantic import BaseModel, Field

class ComputeSize(str, Enum):
    S = "S"
    M = "M"
    L = "L"

class UploadFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"

class UploadMode(str, Enum):
    CREATE = "create"
    APPEND = "append"
    UPSERT = "upsert"
    OVERWRITE = "overwrite"

AppendRequestSingle = Dict[str, Any]
AppendRequestBatch = List[Dict[str, Any]]
AppendRequest = Union[AppendRequestSingle, AppendRequestBatch]

class AppendResponse(BaseModel):
    ok: bool
    error_code: Optional[Literal["invalid-data"]] = None

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

class QueryLogResponse(BaseModel):
    uuid: str
    start_time: str
    end_time: str
    duration_ms: int
    query: str
    session_id: Optional[str] = None
    client_interface: str
    error: Optional[str] = None
    stats: Dict[str, Any]
    progress: int
    visible: bool
    requested_by: str
    user_agent: str

class CancelQueryResponse(BaseModel):
    cancelled: bool
    message: str

class ValidateRequest(BaseModel):
    statement: str

class ValidateResponse(BaseModel):
    valid: bool
    statement: str
    connections_errors: Any
    error: Optional[str] = None

class QueryMetadata(BaseModel):
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)

class QueryResult(BaseModel):
    metadata: QueryMetadata
    rows: List[Any]
