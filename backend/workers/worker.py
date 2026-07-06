from rq import Worker

import backend.workers.jobs  # noqa: F401 — RQ resolves job functions by module path
from backend.app.config import get_settings


def run_worker() -> None:
    import redis as redis_lib

    settings = get_settings()
    connection = redis_lib.from_url(settings.redis_url)
    Worker(settings.redis_queue_name, connection=connection).work(with_scheduler=True)


if __name__ == "__main__":
    run_worker()
