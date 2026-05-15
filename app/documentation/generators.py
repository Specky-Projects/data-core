from typing import Any

from sqlalchemy import Numeric
from sqlalchemy.orm import Session

from app.analytics.registry import analytics_registry
from app.documentation.models import (
    AnalyticsDocumentation,
    CollectorDocumentation,
    EntityRelationship,
    NormalizerDocumentation,
    SchemaDocumentation,
)
from app.documentation.relationships import DEFAULT_ENTITY_RELATIONSHIPS
from app.documentation.schemas import DEFAULT_SCHEMA_DOCUMENTATION
from app.modules.registry import register_pipeline_modules
from app.normalization.registry import normalizer_registry
from collectors.registry import registry as collector_registry
from database.models import Base


class DocumentationGenerator:
    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_defaults(self) -> dict[str, int]:
        register_pipeline_modules()
        return {
            "schemas": self.seed_schema_documentation(),
            "tables": self.seed_table_documentation(),
            "relationships": self.seed_relationships(),
            "collectors": self.seed_collectors(),
            "normalizers": self.seed_normalizers(),
            "analytics": self.seed_analytics(),
        }

    def seed_schema_documentation(self) -> int:
        count = 0
        for item in DEFAULT_SCHEMA_DOCUMENTATION:
            if self._upsert(SchemaDocumentation, item, ["module", "schema_type", "schema_name", "schema_version"]):
                count += 1
        return count

    def seed_table_documentation(self) -> int:
        count = 0
        for table in Base.metadata.sorted_tables:
            module = self._module_for_table(table.name)
            fields = {}
            required = []
            indexes = []
            for column in table.columns:
                fields[column.name] = {
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "foreign_keys": [str(fk.column) for fk in column.foreign_keys],
                    "indexed": column.index,
                    "numeric": isinstance(column.type, Numeric),
                }
                if not column.nullable and not column.primary_key:
                    required.append(column.name)
            for index in table.indexes:
                indexes.append({"name": index.name, "columns": [column.name for column in index.columns]})
            item = {
                "module": module,
                "schema_type": "table",
                "schema_name": table.name,
                "schema_version": "current",
                "description": f"SQLAlchemy table documentation for {table.name}.",
                "fields_json": fields,
                "examples_json": {},
                "validation_rules_json": {"required_columns": required},
                "relationships_json": {
                    "indexes": indexes,
                    "foreign_keys": [
                        {"column": column.name, "references": [str(fk.column) for fk in column.foreign_keys]}
                        for column in table.columns
                        if column.foreign_keys
                    ],
                },
            }
            if self._upsert(SchemaDocumentation, item, ["module", "schema_type", "schema_name", "schema_version"]):
                count += 1
        return count

    def seed_relationships(self) -> int:
        count = 0
        for item in DEFAULT_ENTITY_RELATIONSHIPS:
            if self._upsert(EntityRelationship, item, ["module", "source_entity", "target_entity", "relationship_type"]):
                count += 1
        return count

    def seed_collectors(self) -> int:
        count = 0
        for collector_type in collector_registry.all():
            metadata = collector_type.metadata
            module = "sports_odds" if metadata.domain.value == "sports_betting" else metadata.domain.value
            item = {
                "module": module,
                "source_name": metadata.source,
                "collector_name": metadata.name,
                "collector_version": metadata.collector_version,
                "description": metadata.description,
                "supported_sources_json": [metadata.source],
                "supported_methods_json": ["collector-specific"],
                "raw_schemas_generated_json": [
                    {"schema_name": metadata.raw_schema_name, "schema_version": metadata.raw_schema_version}
                ],
                "limitations_json": ["Collector implementation may have source-specific constraints."],
            }
            if self._upsert(CollectorDocumentation, item, ["collector_name", "collector_version", "source_name"]):
                count += 1
        legacy = {
            "module": "ecommerce",
            "source_name": "poupi_legacy",
            "collector_name": "poupi_legacy_raw_collector",
            "collector_version": "1.0.0",
            "description": "Temporary TypeScript bridge for Poupi Baby legacy scrapers.",
            "supported_sources_json": ["Poupi Baby legacy scrapers"],
            "supported_methods_json": ["npx ts-node raw-bridge.ts"],
            "raw_schemas_generated_json": [{"schema_name": "scrapedProduct", "schema_version": "1.0.0"}],
            "limitations_json": ["Requires Node.js runtime while bridge is active."],
        }
        if self._upsert(CollectorDocumentation, legacy, ["collector_name", "collector_version", "source_name"]):
            count += 1
        return count

    def seed_normalizers(self) -> int:
        count = 0
        for module, normalizer_types in normalizer_registry.all().items():
            for normalizer_type in normalizer_types:
                item = {
                    "module": module,
                    "normalizer_name": normalizer_type.normalizer_name or normalizer_type.__name__,
                    "normalizer_version": normalizer_type.normalizer_version,
                    "supported_raw_schemas_json": [
                        {
                            "schema_name": normalizer_type.supported_raw_schema_name or "*",
                            "schema_version": normalizer_type.supported_raw_schema_version or "*",
                            "source_name": normalizer_type.supported_source_name or "*",
                        }
                    ],
                    "generated_entities_json": [self._normalized_entity_for_module(module)],
                    "validation_rules_json": ["Parser must tolerate missing optional fields."],
                    "quality_expectations_json": ["Record should preserve source lineage fields."],
                }
                if self._upsert(NormalizerDocumentation, item, ["normalizer_name", "normalizer_version"]):
                    count += 1
        return count

    def seed_analytics(self) -> int:
        count = 0
        for module, processor_type in analytics_registry.all().items():
            name = getattr(processor_type, "analytics_processor_name", None) or processor_type.__name__
            version = getattr(processor_type, "analytics_processor_version", "1.0.0")
            item = {
                "module": module,
                "analytics_name": name,
                "analytics_version": version,
                "input_entities_json": [self._normalized_entity_for_module(module)],
                "output_entities_json": [self._analytics_entity_for_module(module)],
                "generated_metrics_json": self._metrics_for_module(module),
                "dependencies_json": ["normalized data"],
            }
            if self._upsert(AnalyticsDocumentation, item, ["analytics_name", "analytics_version"]):
                count += 1
        return count

    def _upsert(self, model: type, item: dict[str, Any], identity_fields: list[str]) -> bool:
        query = self.db.query(model)
        for field in identity_fields:
            query = query.filter(getattr(model, field) == item[field])
        existing = query.one_or_none()
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
            return False
        self.db.add(model(**item))
        return True

    @staticmethod
    def _normalized_entity_for_module(module: str) -> str:
        return {
            "ecommerce": "normalized_products",
            "real_estate": "normalized_real_estate_listings",
            "crypto": "normalized_crypto_snapshots",
            "trading": "normalized_market_candles",
            "sports_odds": "normalized_sports_odds",
        }.get(module, f"normalized_{module}")

    @staticmethod
    def _analytics_entity_for_module(module: str) -> str:
        return {
            "ecommerce": "product_price_analytics",
            "real_estate": "real_estate_analytics",
            "crypto": "crypto_analytics",
            "trading": "trading_analytics",
            "sports_odds": "sports_odds_analytics",
        }.get(module, f"{module}_analytics")

    @staticmethod
    def _metrics_for_module(module: str) -> list[str]:
        return {
            "ecommerce": ["avg_price_7d", "avg_price_30d", "min_price_90d", "max_price_90d", "price_score"],
            "real_estate": ["price_per_m2", "neighborhood_avg_price_m2", "opportunity_score"],
            "crypto": ["volatility_24h", "volume_spike_score", "trend_score", "regime"],
            "trading": ["rsi", "moving_average_fast", "moving_average_slow", "atr", "trend_score"],
            "sports_odds": ["opening_odd", "current_odd", "line_movement", "clv", "ev_estimate"],
        }.get(module, [])

    @staticmethod
    def _module_for_table(table_name: str) -> str:
        if "real_estate" in table_name:
            return "real_estate"
        if "sports" in table_name or "odds" in table_name:
            return "sports_odds"
        if "crypto" in table_name:
            return "crypto"
        if "trading" in table_name or "market_candles" in table_name:
            return "trading"
        if "product" in table_name or "ecommerce" in table_name:
            return "ecommerce"
        if table_name in {"raw_collections", "collection_runs", "collection_targets", "collector_versions", "collector_documentation"}:
            return "raw"
        if "normalizer" in table_name or table_name.startswith("normalized_"):
            return "normalization"
        if "analytics" in table_name:
            return "analytics"
        if "documentation" in table_name or table_name in {"data_lineage", "entity_relationships"}:
            return "documentation"
        return "core"
