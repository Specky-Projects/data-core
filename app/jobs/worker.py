import argparse
import signal
import time

from core.config import settings
from logs.config import configure_logging
from scheduler.jobs import analytics_job, normalize_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Data Core pipeline worker.")
    parser.add_argument("--interval", type=int, default=settings.worker_pipeline_interval_seconds)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    configure_logging()
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while running:
        normalize_job()
        analytics_job()
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
