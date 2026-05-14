import argparse

from app.modules.registry import register_pipeline_modules
from app.normalization.registry import normalizer_registry
from app.raw.models import RawCollection
from database.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Reprocess versioned RAW records with a selected normalizer.")
    parser.add_argument("--module", required=True)
    parser.add_argument("--source", required=False)
    parser.add_argument("--raw-schema", required=True)
    parser.add_argument("--raw-schema-version", required=True)
    parser.add_argument("--normalizer-version", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    register_pipeline_modules()
    db = SessionLocal()
    try:
        query = db.query(RawCollection).filter(
            RawCollection.module == args.module,
            RawCollection.raw_schema_name == args.raw_schema,
            RawCollection.raw_schema_version == args.raw_schema_version,
        )
        if args.source:
            query = query.filter(RawCollection.source_name == args.source)
        raws = query.order_by(RawCollection.collected_at).limit(args.limit).all()

        processed = 0
        for raw in raws:
            normalizer_type = normalizer_registry.get_for_raw(
                raw.module,
                source_name=raw.source_name,
                raw_schema_name=raw.raw_schema_name,
                raw_schema_version=raw.raw_schema_version,
            )
            if not normalizer_type:
                continue
            normalizer = normalizer_type(db)
            if normalizer.normalizer_version != args.normalizer_version:
                continue
            normalized = normalizer.normalize(raw)
            saved = normalizer.save_normalized(raw, normalized)
            if saved:
                normalizer.stamp_normalized(raw)
                normalizer.ensure_normalizer_version(raw)
                processed += saved
            db.commit()

        print({"processed": processed, "raw_loaded": len(raws)})
    finally:
        db.close()


if __name__ == "__main__":
    main()
