from app.documentation.services import DocumentationService
from database.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        print(DocumentationService(db).ensure_defaults())
    finally:
        db.close()


if __name__ == "__main__":
    main()
