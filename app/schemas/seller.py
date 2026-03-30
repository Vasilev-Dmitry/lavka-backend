from pydantic import BaseModel, Field, EmailStr, UUID4, ConfigDict
from datetime import datetime

class SellerLogin(BaseModel):
    email: EmailStr

class SellerVerify(BaseModel):
    code: UUID4 = Field(description="Verification code")

class SellerResponse(BaseModel):
    email: EmailStr
    is_subscribed: bool | None = None
    subscription_expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)