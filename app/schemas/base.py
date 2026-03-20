from pydantic import BaseModel

class Response(BaseModel):
    success: bool
    message: str

class ErrorMessage(BaseModel):
    detail: str