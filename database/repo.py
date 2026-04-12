import json
import time
import socket
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import SessionLocal
from . import models


def _to_dict(job) -> dict:
    if job is None:
        return None
    return {
        "telegram_update_id": job.telegram_update_id,
        "user_id": job.user_id,
        "chat_id": job.chat_id,
        "raw_update": job.raw_update,
        "status": job.status,
        "pipeline": job.pipeline,
        "attempts": job.attempts,
        "available_at": job.available_at,
        "locked_at": job.locked_at,
        "locked_by": job.locked_by,
        "error": job.error,
        "result_preview": job.result_preview,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def init_db():
    from . import models as _m
    from . import engine as _engine

    _m.Base.metadata.create_all(bind=_engine)


def create_job_from_update(update_body: dict) -> dict:
    update_id = update_body.get("update_id")
    if update_id is None:
        return None
    with SessionLocal() as session:
        existing = session.execute(
            select(models.MessageJob).where(
                models.MessageJob.telegram_update_id == update_id
            )
        ).scalar_one_or_none()
        if existing:
            return _to_dict(existing)
        from time import time
        from json import dumps

        user_id = update_body.get("message", {}).get("from", {}).get("id")
        chat_id = update_body.get("message", {}).get("chat", {}).get("id")
        j = models.MessageJob(
            telegram_update_id=update_id,
            user_id=user_id,
            chat_id=chat_id,
            raw_update=dumps(update_body),
            status="queued",
            pipeline=None,
            attempts=0,
            available_at=time(),
            created_at=time(),
            updated_at=time(),
        )
        session.add(j)
        session.commit()
        return _to_dict(j)


def claim_next_job() -> dict:
    with SessionLocal() as session:
        stmt = (
            select(models.MessageJob)
            .where(models.MessageJob.status == "queued")
            .order_by(models.MessageJob.id)
            .limit(1)
        )
        job = session.execute(stmt).scalar_one_or_none()
        if not job:
            return None
        job.status = "running"
        job.locked_at = time.time()
        job.locked_by = socket.gethostname()
        job.attempts = (job.attempts or 0) + 1
        session.commit()
        return _to_dict(job)


def update_job_by_update_id(update_id: int, **kwargs) -> bool:
    with SessionLocal() as session:
        job = session.execute(
            select(models.MessageJob).where(
                models.MessageJob.telegram_update_id == update_id
            )
        ).scalar_one_or_none()
        if not job:
            return False
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)
        job.updated_at = time.time()
        session.commit()
        return True


def get_job_by_update_id(update_id: int):
    with SessionLocal() as session:
        job = session.execute(
            select(models.MessageJob).where(
                models.MessageJob.telegram_update_id == update_id
            )
        ).scalar_one_or_none()
        return _to_dict(job)


def list_jobs(limit: int | None = None):
    with SessionLocal() as session:
        stmt = select(models.MessageJob).order_by(models.MessageJob.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        jobs = session.execute(stmt).scalars().all()
        return [_to_dict(j) for j in jobs]


def list_jobs(limit: int | None = None):
    with SessionLocal() as session:
        stmt = select(models.MessageJob).order_by(models.MessageJob.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        jobs = session.execute(stmt).scalars().all()
        return [_to_dict(j) for j in jobs]
