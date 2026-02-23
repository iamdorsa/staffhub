import os
import subprocess
import sys

os.environ["DATABASE_URL"] = "mysql+pymysql://root:root@127.0.0.1:3306/staffhub_db?charset=utf8mb4"
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=os.path.join(os.path.dirname(__file__), "..", "db"),
    env={**os.environ},
    check=True,
)
