from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import db_session
from app.documentation.services import DocumentationService

router = APIRouter(prefix="/api/v1/documentation", tags=["documentation"])


class DataContractUpsert(BaseModel):
    module: str
    source_name: str | None = None
    contract_name: str | None = None
    contract_version: str = "1.0.0"
    owner_name: str = "data-platform"
    freshness_sla: str = "not_defined"
    criticality: str = "medium"
    status: str = "draft"
    raw_required: bool = True
    lineage_required: bool = True
    quality_required: bool = True
    schema_rules_json: dict[str, Any] | list[Any] = Field(default_factory=dict)
    quality_rules_json: dict[str, Any] | list[Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DataContractPatch(BaseModel):
    source_name: str | None = None
    contract_name: str | None = None
    contract_version: str | None = None
    owner_name: str | None = None
    freshness_sla: str | None = None
    criticality: str | None = None
    status: str | None = None
    raw_required: bool | None = None
    lineage_required: bool | None = None
    quality_required: bool | None = None
    schema_rules_json: dict[str, Any] | list[Any] | None = None
    quality_rules_json: dict[str, Any] | list[Any] | None = None
    metadata_json: dict[str, Any] | None = None


class DataOwnerUpsert(BaseModel):
    module: str
    owner_name: str
    technical_contact: str | None = None
    business_contact: str | None = None
    description: str | None = None
    is_active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DataOwnerPatch(BaseModel):
    owner_name: str | None = None
    technical_contact: str | None = None
    business_contact: str | None = None
    description: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class DataSlaUpsert(BaseModel):
    module: str
    source_name: str | None = None
    freshness_sla: str = "not_defined"
    availability_sla: str | None = None
    quality_sla: str | None = None
    is_active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DataSlaPatch(BaseModel):
    source_name: str | None = None
    freshness_sla: str | None = None
    availability_sla: str | None = None
    quality_sla: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


@router.get("/schemas")
def list_schemas(
    db: Session = Depends(db_session),
    module: str | None = None,
    schema_type: str | None = None,
) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return [_to_dict(row) for row in service.schemas(module=module, schema_type=schema_type)]


@router.get("/schemas/{name}")
def get_schema_documentation(name: str, db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    rows = service.schemas(name=name)
    if not rows:
        raise HTTPException(status_code=404, detail="Schema documentation not found")
    return [_to_dict(row) for row in rows]


@router.get("/lineage/{raw_collection_id}")
def get_lineage(raw_collection_id: UUID, db: Session = Depends(db_session)) -> dict[str, Any]:
    return DocumentationService(db).lineage(raw_collection_id)


@router.get("/relationships")
def list_relationships(db: Session = Depends(db_session), module: str | None = None) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return [_to_dict(row) for row in service.relationships(module=module)]


@router.get("/collectors")
def list_collector_documentation(
    db: Session = Depends(db_session),
    module: str | None = None,
    source_name: str | None = None,
) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return [_to_dict(row) for row in service.collectors(module=module, source_name=source_name)]


@router.get("/normalizers")
def list_normalizer_documentation(db: Session = Depends(db_session), module: str | None = None) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return [_to_dict(row) for row in service.normalizers(module=module)]


@router.get("/analytics")
def list_analytics_documentation(db: Session = Depends(db_session), module: str | None = None) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return [_to_dict(row) for row in service.analytics(module=module)]


@router.get("/catalog")
def get_data_catalog(db: Session = Depends(db_session), module: str | None = None) -> dict[str, Any]:
    return DocumentationService(db).catalog(module=module)


@router.get("/coverage")
def get_coverage(
    db: Session = Depends(db_session),
    module: str | None = None,
    source_name: str | None = None,
    raw_schema_name: str | None = None,
    collector_version: str | None = None,
    normalizer_version: str | None = None,
) -> dict[str, Any]:
    return DocumentationService(db).coverage(
        module=module,
        source_name=source_name,
        raw_schema_name=raw_schema_name,
        collector_version=collector_version,
        normalizer_version=normalizer_version,
    )


@router.get("/tables")
def list_table_documentation(
    db: Session = Depends(db_session),
    module: str | None = None,
    schema_name: str | None = None,
) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return [
        _to_dict(row)
        for row in service.schemas(name=schema_name, module=module, schema_type="table")
    ]


@router.get("/erd")
def get_erd(db: Session = Depends(db_session), module: str | None = None) -> dict[str, Any]:
    return DocumentationService(db).erd(module=module)


@router.get("/openapi-extension")
def get_openapi_extension(db: Session = Depends(db_session), module: str | None = None) -> dict[str, Any]:
    return DocumentationService(db).openapi_extension(module=module)


@router.get("/contracts")
def list_data_contracts(db: Session = Depends(db_session), module: str | None = None) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return service.data_contracts(module=module)


@router.post("/contracts")
def upsert_data_contract(payload: DataContractUpsert, db: Session = Depends(db_session)) -> dict[str, Any]:
    return DocumentationService(db).upsert_contract(payload.model_dump())


@router.patch("/contracts/{contract_id}")
def update_data_contract(
    contract_id: UUID,
    payload: DataContractPatch,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    updated = DocumentationService(db).update_contract(contract_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Data contract not found")
    return updated


@router.delete("/contracts/{contract_id}")
def delete_data_contract(contract_id: UUID, db: Session = Depends(db_session)) -> dict[str, bool]:
    deleted = DocumentationService(db).delete_contract(contract_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data contract not found")
    return {"deleted": True}


@router.get("/owners")
def list_data_owners(db: Session = Depends(db_session), module: str | None = None) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return service.owners(module=module)


@router.post("/owners")
def upsert_data_owner(payload: DataOwnerUpsert, db: Session = Depends(db_session)) -> dict[str, Any]:
    return DocumentationService(db).upsert_owner(payload.model_dump())


@router.patch("/owners/{owner_id}")
def update_data_owner(
    owner_id: UUID,
    payload: DataOwnerPatch,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    updated = DocumentationService(db).update_owner(owner_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Data owner not found")
    return updated


@router.delete("/owners/{owner_id}")
def delete_data_owner(owner_id: UUID, db: Session = Depends(db_session)) -> dict[str, bool]:
    deleted = DocumentationService(db).delete_owner(owner_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data owner not found")
    return {"deleted": True}


@router.get("/slas")
def list_data_slas(db: Session = Depends(db_session), module: str | None = None) -> list[dict[str, Any]]:
    service = DocumentationService(db)
    service.ensure_defaults()
    return service.slas(module=module)


@router.post("/slas")
def upsert_data_sla(payload: DataSlaUpsert, db: Session = Depends(db_session)) -> dict[str, Any]:
    return DocumentationService(db).upsert_sla(payload.model_dump())


@router.patch("/slas/{sla_id}")
def update_data_sla(
    sla_id: UUID,
    payload: DataSlaPatch,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    updated = DocumentationService(db).update_sla(sla_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Data SLA not found")
    return updated


@router.delete("/slas/{sla_id}")
def delete_data_sla(sla_id: UUID, db: Session = Depends(db_session)) -> dict[str, bool]:
    deleted = DocumentationService(db).delete_sla(sla_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data SLA not found")
    return {"deleted": True}


@router.post("/lineage/backfill")
def backfill_lineage(
    db: Session = Depends(db_session),
    module: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, int]:
    return DocumentationService(db).backfill_lineage(module=module, limit=limit)


def _to_dict(row: object) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}
