"""Worker process: `python -m app.worker`

Runs separately from the API. In Kubernetes this is its own Deployment, which
you can scale independently (or autoscale on queue length with KEDA).
"""

import logging

from rq import Worker

from app.cache import redis_queue
from app.config import settings
from app.db import init_db

QUEUE_NAME = "ingest"


def main() -> None:
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s [worker] %(name)s: %(message)s"
    )
    init_db()
    Worker([QUEUE_NAME], connection=redis_queue).work(with_scheduler=False)


if __name__ == "__main__":
    main()
