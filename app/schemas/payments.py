from pydantic import BaseModel, Field

class InvoiceCreated(BaseModel):
    link: str = Field(description="Payment link")