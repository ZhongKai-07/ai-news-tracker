from __future__ import annotations
from datetime import date
from sqlalchemy import Date, Float, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"
    __table_args__ = (UniqueConstraint("keyword_id", "date", name="uq_keyword_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    date: Mapped[date] = mapped_column(Date)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    keyword = relationship("Keyword", back_populates="snapshots")
