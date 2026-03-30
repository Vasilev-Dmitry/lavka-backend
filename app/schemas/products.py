from pydantic import BaseModel, Field, ConfigDict, UUID4
from decimal import Decimal

class CreateProduct(BaseModel):
    name: str = Field(description="Product name", min_length=3, max_length=64)
    description: str = Field(description="Product description", min_length=3, max_length=512)
    price: Decimal
    characteristics: dict | None = None

class UpdateProduct(BaseModel):
    name: str | None = Field(None, description="Product name", min_length=3, max_length=64)
    description: str | None = Field(None, description="Product description", min_length=3, max_length=512)
    price: Decimal | None = None
    characteristics: dict | None = None

class ProductResponse(BaseModel):
    id: UUID4
    name: str
    description: str | None
    price: Decimal
    characteristics: dict | None
    images: list[str] | None

    model_config = ConfigDict(from_attributes=True)