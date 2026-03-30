from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, Date, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class TrendReport(Base):
    __tablename__ = "trend_reports"
    __table_args__ = (UniqueConstraint("keyword_id", "report_date", "period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    report_date: Mapped[date] = mapped_column(Date)
    period: Mapped[str] = mapped_column(String(10))
    summary: Mapped[str] = mapped_column(Text)
    key_drivers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    outlook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    keyword = relationship("Keyword")
