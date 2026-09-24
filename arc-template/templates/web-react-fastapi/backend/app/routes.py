from fastapi import APIRouter

from .models import ModuleSummary
from .repository import repository


router = APIRouter()


@router.get("/modules", response_model=list[ModuleSummary])
def list_modules() -> list[ModuleSummary]:
    return repository.list_modules()


@router.post("/modules", response_model=ModuleSummary)
def upsert_module(module: ModuleSummary) -> ModuleSummary:
    return repository.upsert_module(module)

