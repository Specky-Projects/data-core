import argparse

from app.documentation.services import DocumentationService
from database.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Data Core lineage.")
    parser.add_argument("--module", required=False)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(DocumentationService(db).backfill_lineage(module=args.module, limit=args.limit))
    finally:
        db.close()


if __name__ == "__main__":
    main()
