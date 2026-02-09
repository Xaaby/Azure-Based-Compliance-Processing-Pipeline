import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://appuser:apppassword@localhost:5433/compliance_db",
)

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema():
    """Initialize database schema from sql/schema.sql if available."""
    schema_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
    if not schema_path.exists():
        return

    with engine.connect() as conn:
        sql_text = schema_path.read_text(encoding="utf-8")
        for statement in filter(None, (s.strip() for s in sql_text.split(";"))):
            if statement:
                conn.execute(text(statement))
        conn.commit()


