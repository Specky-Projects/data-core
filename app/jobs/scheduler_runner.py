import signal
import time

from logs.config import configure_logging
from scheduler.service import create_scheduler, start_scheduler, stop_scheduler


def main() -> None:
    configure_logging()
    scheduler = create_scheduler()
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    start_scheduler(scheduler)
    try:
        while running:
            time.sleep(1)
    finally:
        stop_scheduler(scheduler)


if __name__ == "__main__":
    main()
