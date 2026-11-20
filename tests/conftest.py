import os

# Tests must not depend on a developer's .env or on a running Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
