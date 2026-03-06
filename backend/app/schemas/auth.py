from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=2, max_length=255)
    last_name: str = Field(min_length=2, max_length=255)
    restaurant: str = Field(min_length=2, max_length=255)
    job_title: str = Field(min_length=2, max_length=255)
    desired_login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    login: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
