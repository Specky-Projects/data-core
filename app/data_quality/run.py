import argparse

from app.data_quality.services import DataQualityService
from database.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Data Core data quality checks.")
    parser.add_argument("--module", required=False)
    parser.add_argument("--source", required=False, dest="source_name")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(DataQualityService(db).run(module=args.module, source_name=args.source_name, limit=args.limit))
    finally:
        db.close()


if __name__ == "__main__":
    main()
