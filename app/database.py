from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import STORAGE_DIR

DATABASE_URL = f"sqlite:///{(STORAGE_DIR / 'jobs.db').as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
