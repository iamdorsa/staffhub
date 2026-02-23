from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth import service
from src.modules.auth.schemas import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    tokens = service.login_with_password(db, body.username, body.password)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    tokens = service.refresh_access_token(db, body.refresh_token)
    return TokenResponse(**tokens)
