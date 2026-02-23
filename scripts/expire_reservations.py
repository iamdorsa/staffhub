"""Background job: expire pending reservations past the 72-hour admin deadline.

Can be called via cron or a simple scheduler:
    python -m scripts.expire_reservations
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "db"))

from src.core.database import SessionLocal
from src.modules.accommodation.service import expire_pending_reservations


def main() -> None:
    db = SessionLocal()
    try:
        count = expire_pending_reservations(db)
        print(f"Auto-approved {count} reservation(s), expired the rest.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
