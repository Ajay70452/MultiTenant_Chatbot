from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.config import DATABASE_URL
import time
import logging
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _init_engine_and_session():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(DATABASE_URL)
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine, _SessionLocal


def wait_for_db(retries: int = 5, delay: float = 2.0, engine_obj=None):
    """Wait for the database to become available.

    Args:
        retries: number of times to retry before giving up.
        delay: seconds to wait between retries.
        engine_obj: optional SQLAlchemy engine to use (for testing).
    Returns:
        True if DB became available, False otherwise.
    """
    if engine_obj is None:
        # initialize engine lazily (don't import DB driver at test collection time)
        engine_obj, _ = _init_engine_and_session()

    attempt = 0
    while attempt <= retries:
        try:
            conn = engine_obj.connect()
            conn.close()
            logger.info("Database is available")
            return True
        except Exception as e:
            # Catch any exception during connect (OperationalError or others)
            logger.warning(f"Database unavailable (attempt {attempt}/{retries}): {e}")
            attempt += 1
            if attempt > retries:
                logger.error("Exceeded max retries waiting for database")
                return False
            time.sleep(delay)


def get_db():
    if _SessionLocal is None:
        _init_engine_and_session()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()