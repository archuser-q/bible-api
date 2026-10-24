from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)  # 1 = Genesis ... 66 = Revelation
    name: Mapped[str] = mapped_column(String(64), unique=True)
    testament: Mapped[str] = mapped_column(String(2))  # "OT" hoặc "NT"
    chapter_count: Mapped[int]


class Verse(Base):
    __tablename__ = "verses"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    chapter: Mapped[int]
    verse: Mapped[int]
    text: Mapped[str] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("book_id", "chapter", "verse"),)

class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int]
    chapter: Mapped[int]
    verse: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )