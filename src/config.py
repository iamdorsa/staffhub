import sys
from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_MODELS_PATH = PROJECT_ROOT / "db"
if str(DB_MODELS_PATH) not in sys.path:
    sys.path.insert(0, str(DB_MODELS_PATH))


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str

    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    OTP_EXPIRY_SECONDS: int = 300
    OTP_LENGTH: int = 6
    SMS_PROVIDER: str = "console"
    SMS_API_KEY: str = ""

    RESERVATION_ADMIN_DEADLINE_HOURS: int = 72
    BOOKING_WINDOW_DAYS: int = 20
    MAX_STAY_NIGHTS: int = 3
    MAX_PERSONS_PER_RESERVATION: int = 8
    MAX_EXTRA_GUESTS: int = 2

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
