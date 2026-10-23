from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.embeddings import EMBEDDING_DIM


class Book(Base):
    __tablename__ = "books"

    # id = thứ tự sách trong Kinh Thánh (1 = Genesis ... 66 = Revelation)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    testament: Mapped[str] = mapped_column(String(2))  # "OT" (Cựu Ước) | "NT" (Tân Ước)
    chapter_count: Mapped[int]

    verses: Mapped[list["Verse"]] = relationship(back_populates="book")


class Verse(Base):
    __tablename__ = "verses"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    chapter: Mapped[int]
    verse: Mapped[int]
    text: Mapped[str] = mapped_column(Text)

    # Cột do PostgreSQL tự tính, dùng cho full-text search
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', text)", persisted=True),
        deferred=True,
    )

    # Vector ý nghĩa của câu, dùng cho semantic search (tạo bằng scripts.embed_verses)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True, deferred=True
    )

    book: Mapped[Book] = relationship(back_populates="verses")

    __table_args__ = (
        UniqueConstraint("book_id", "chapter", "verse", name="uq_verse_ref"),
        Index("ix_verses_book_chapter", "book_id", "chapter"),
        Index("ix_verses_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_verses_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
