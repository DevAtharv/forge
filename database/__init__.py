import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Lightweight database setup. Default to SQLite for dev; can be overridden with DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///forge.db")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    from . import models

    models.Base.metadata.create_all(bind=engine)
