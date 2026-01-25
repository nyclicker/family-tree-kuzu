import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,           # Increase from default 5 to 20
    max_overflow=30,        # Increase from default 10 to 30
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_timeout=60,        # Increase timeout from 30 to 60 seconds
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
