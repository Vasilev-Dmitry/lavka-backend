from pydantic import BaseModel, Field, ConfigDict

class CreateShop(BaseModel):
    name: str = Field(min_length=3, max_length=64)
    description: str | None = Field(None, min_length=3, max_length=256)

class UpdateShop(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=64)
    description: str | None = Field(None, min_length=3, max_length=256)

class ConnectDomain(BaseModel):
    domain: str = Field(min_length=3, max_length=63)

class ShopResponse(BaseModel):
    name: str
    description: str | None = None
    logo: str | None = None
    domain: str | None = None

    model_config = ConfigDict(from_attributes=True)