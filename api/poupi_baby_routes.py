from fastapi import APIRouter

from domains.poupi_baby.interface import get_interface_summary, list_endpoints, list_modules

router = APIRouter(prefix="/api/v1/poupi-baby", tags=["poupi-baby"])


@router.get("")
def summary() -> dict:
    return get_interface_summary()


@router.get("/modules")
def modules() -> list[dict]:
    return list_modules()


@router.get("/endpoints")
def endpoints() -> list[dict]:
    return list_endpoints()

