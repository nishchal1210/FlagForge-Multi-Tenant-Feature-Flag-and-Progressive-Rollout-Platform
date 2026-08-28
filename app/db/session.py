
from collections.abc import Generator

# Generator type, used to describe the behavior of get_db():
# it gives FastAPI a database session and later performs cleanup.

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Session: represents an active unit of database work.
# sessionmaker: creates new sessions when needed.

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)

# calling get_db opens a database session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()