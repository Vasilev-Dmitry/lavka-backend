from decimal import Decimal
from pydantic import BaseModel, UUID4, ConfigDict

class ShowcaseResponse(BaseModel):
    domain: str
    name: str
    description: str
    logo: str | None

    model_config = ConfigDict(from_attributes=True)

class ShowcaseProduct(BaseModel):
    id: UUID4
    name: str
    description: str | None
    price: Decimal
    characteristics: dict | None
    images: list[str] | None

    model_config = ConfigDict(from_attributes=True)