from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, BigInteger, String, Float, Text
import json

Base = declarative_base()


class MessageJob(Base):
    __tablename__ = "message_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_update_id = Column(Integer, unique=True, index=True, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=True)
    raw_update = Column(Text, nullable=True)  # JSON string
    status = Column(String(32), nullable=False, default="queued")
    pipeline = Column(Text, nullable=True)  # JSON string
    attempts = Column(Integer, default=0)
    available_at = Column(Float, default=0.0)
    locked_at = Column(Float, nullable=True)
    locked_by = Column(String(128), nullable=True)
    error = Column(Text, nullable=True)
    result_preview = Column(Text, nullable=True)
    created_at = Column(Float, nullable=True)
    updated_at = Column(Float, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    summary = Column(Text, nullable=True)
    active_context = Column(Text, nullable=True)
    last_context_refresh = Column(Float, nullable=True)
    # Additional fields carried over from the draft in a real implementation
    preferences = Column(Text, nullable=True)
