from typing import Optional

class AltertableLakehouseError(Exception):
    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause

class NetworkError(AltertableLakehouseError): 
    pass

class TimeoutError(AltertableLakehouseError): 
    pass

class SerializationError(AltertableLakehouseError): 
    pass

class ParseError(AltertableLakehouseError):
    def __init__(self, message: str, line_index: int, raw_content: str):
        super().__init__(f"{message} at line {line_index}: {raw_content}")
        self.line_index = line_index
        self.raw_content = raw_content

class ApiError(AltertableLakehouseError):
    def __init__(self, message: str, status_code: int):
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code

class AuthError(ApiError): 
    pass

class BadRequestError(ApiError): 
    pass

class ConfigurationError(AltertableLakehouseError): 
    pass
