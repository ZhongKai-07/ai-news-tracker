from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DataSource

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    type: str = "rss"
    url: str
    parser_config: str | None = None
    auth_config: str | None = None
    schedule: str | None = None
    weight: float = 1.0
    proxy_url: str | None = None
    custom_headers: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    url: str | None = None
    parser_config: str | None = None
    auth_config: str | None = None
    schedule: str | None = None
    weight: float | None = None
    enabled: bool | None = None
    proxy_url: str | None = None
    custom_headers: str | None = None


class SourceResponse(BaseModel):
    id: int
    name: str
    type: str
    url: str
    weight: float
    enabled: bool
    status: str
    last_fetched_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int
    proxy_url: str | None = None
    custom_headers: str | None = None

    class Config:
        from_attributes = True


@router.post("", response_model=SourceResponse)
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    source = DataSource(**data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("", response_model=list[SourceResponse])
async def list_sources(include_disabled: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(DataSource)
    if not include_disabled:
        query = query.where(DataSource.status != "disabled")
    result = await db.execute(query)
    return result.scalars().all()


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, data: SourceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    # Soft delete — disable instead of physical delete to preserve article history
    source.enabled = False
    source.status = "disabled"
    await db.commit()
    return {"status": "deleted", "id": source_id}
