"""Tạo embedding cho toàn bộ câu Kinh Thánh và lưu vào cột verses.embedding.

Cách chạy:
    python -m scripts.embed_verses          # chỉ xử lý các câu chưa có embedding
    python -m scripts.embed_verses --all    # tạo lại từ đầu (ví dụ sau khi đổi mô hình)

Chạy dở mà dừng (Ctrl+C) thì lần sau chạy lại sẽ làm tiếp, không mất phần đã xong.
"""

import sys
import time

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, select, text, update

from app.config import settings
from app.database import engine
from app.embeddings import EMBEDDING_DIM, embed_passages
from app.models import Verse

BATCH_SIZE = 256


def ensure_schema() -> None:
    """Database tạo từ phiên bản cũ chưa có cột embedding -> thêm vào."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text(f"ALTER TABLE verses ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})")
        )


def create_index() -> None:
    """Tạo index HNSW sau khi có dữ liệu (nhanh hơn tạo trước rồi chèn dần)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_verses_embedding "
                "ON verses USING hnsw (embedding vector_cosine_ops)"
            )
        )


def main(redo_all: bool) -> None:
    ensure_schema()

    with engine.begin() as conn:
        if redo_all:
            conn.execute(update(Verse.__table__).values(embedding=None))
        rows = conn.execute(
            select(Verse.id, Verse.text).where(Verse.embedding.is_(None)).order_by(Verse.id)
        ).all()

    total = len(rows)
    if total == 0:
        print("Tất cả câu đã có embedding.")
        create_index()
        return

    print(f"Mô hình: {settings.embedding_model} — cần xử lý {total} câu")
    if total > 1000:
        # Ghi hàng loạt khi đang có index HNSW chậm hơn nhiều -> xóa, ghi xong tạo lại
        with engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_verses_embedding"))
    table = Verse.__table__
    stmt = (
        update(table)
        .where(table.c.id == bindparam("verse_id"))
        .values(embedding=bindparam("vec", type_=Vector(EMBEDDING_DIM)))
    )

    started = time.perf_counter()
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        vectors = embed_passages([r.text for r in batch])

        with engine.begin() as conn:  # commit từng batch để chạy lại được
            conn.execute(stmt, [{"verse_id": r.id, "vec": v} for r, v in zip(batch, vectors)])

        done = min(i + BATCH_SIZE, total)
        speed = done / (time.perf_counter() - started)
        print(f"  {done}/{total} ({done * 100 // total}%) — {speed:.0f} câu/giây", flush=True)

    create_index()
    print(f"Xong sau {time.perf_counter() - started:.0f} giây.")


if __name__ == "__main__":
    main(redo_all="--all" in sys.argv)
