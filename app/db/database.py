import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# SQLite needs check_same_thread=False because FastAPI
# runs in multiple threads and SQLite by default only
# allows the thread that created the connection to use it
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db():
    """
    Creates all database tables if they do not exist.
    Safe to call multiple times — will not drop existing data.
    Called once when the application starts up.
    """
    from app.db import models
    Base.metadata.create_all(bind=engine)
    logger.info("[DB] Database initialized successfully")


def get_db():
    """
    Provides a database session.
    Closes the session automatically when done.
    Used as a dependency in FastAPI routes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()