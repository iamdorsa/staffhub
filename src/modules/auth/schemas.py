from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class OtpSendRequest(BaseModel):
    username: str


class OtpSendResponse(BaseModel):
    message: str


class OtpVerifyRequest(BaseModel):
    username: str
    otp_code: str
