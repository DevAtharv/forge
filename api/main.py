from fastapi import FastAPI, Request, HTTPException
import os, time, socket
from database import repo as job_repo

app = FastAPI(title="Forge MVP API")


@app.post("/webhook")
async def webhook(req: Request):
    secret = req.headers.get("X-Telegram-Secret")
    if secret != (os.environ.get("TELEGRAM_SECRET")):
        raise HTTPException(status_code=401, detail="Invalid Telegram secret")
    body = await req.json()
    update_id = body.get("update_id")
    if update_id is None:
        return {"status": "ignored"}
    # Persist to durable job queue via repository
    job = job_repo.create_job_from_update(body)
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup():
    # Start a lightweight worker loop in the background if available
    try:
        from workers.worker import start_worker
        import asyncio

        # Initialize DB and start worker
        try:
            from database import repo as job_repo

            job_repo.init_db()
        except Exception:
            pass
        app.state.worker_task = asyncio.create_task(start_worker())
    except Exception as e:
        # Not fatal; the MVP can run with manual starts
        print(f"Warning: could not start worker automatically: {e}")
