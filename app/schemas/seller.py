from pydantic import BaseModel, Field, EmailStr, UUID4

class SellerLogin(BaseModel):
    email: EmailStr = Field(description="Email")

class SellerVerify(BaseModel):
    code: UUID4 = Field(description="Verification code")