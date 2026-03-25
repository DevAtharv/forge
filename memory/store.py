import time
import socket


class InMemoryStore:
    def __init__(self):
        # key: telegram_update_id -> job dict
        self.jobs = {}

    def persist_job(self, job: dict) -> bool:
        upd = job.get("telegram_update_id")
        if upd is None:
            return False
        if upd in self.jobs:
            # deduplicate: ignore duplicates
            return False
        self.jobs[upd] = job
        return True

    def get_job(self, update_id: int) -> dict:
        return self.jobs.get(update_id)

    def claim_next(self) -> dict:
        now = time.time()
        for upd, job in list(self.jobs.items()):
            if job.get("status") == "queued":
                job["status"] = "running"
                job["locked_at"] = now
                job["locked_by"] = socket.gethostname()
                job["attempts"] = job.get("attempts", 0) + 1
                self.jobs[upd] = job
                return job
        return None

    def update_job(self, update_id: int, **kwargs) -> bool:
        if update_id in self.jobs:
            self.jobs[update_id].update(kwargs)
            return True
        return False

    def all_jobs(self):
        return list(self.jobs.values())
