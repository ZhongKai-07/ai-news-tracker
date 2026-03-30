from datetime import date
from typing import Optional
from sqlalchemy import Integer, Text, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class KeywordCorrelation(Base):
    __tablename__ = "keyword_correlations"
    __table_args__ = (
        UniqueConstraint("keyword_id_a", "keyword_id_b", "period_start", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_id_a: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    keyword_id_b: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    co_occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    relationship_desc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    keyword_a = relationship("Keyword", foreign_keys=[keyword_id_a])
    keyword_b = relationship("Keyword", foreign_keys=[keyword_id_b])
