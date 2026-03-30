from __future__ import annotations
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class KeywordMention(Base):
    __tablename__ = "keyword_mentions"
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey("articles.id"))
    match_location: Mapped[str] = mapped_column(String(20))
    context_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keyword = relationship("Keyword", back_populates="mentions")
    article = relationship("Article", back_populates="mentions")
