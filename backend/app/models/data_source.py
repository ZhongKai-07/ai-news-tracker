from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String, Float, Boolean, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(String(500))
    parser_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="normal")
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    proxy_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    custom_headers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    articles = relationship("Article", back_populates="source")
