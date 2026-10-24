from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
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