"""Import dữ liệu Kinh Thánh từ file JSON của repo mdbible vào PostgreSQL.

Cách chạy:
    python -m scripts.import_bible data/mdbible/json/ESV.json

Script chạy lại nhiều lần được: mỗi lần chạy sẽ xóa dữ liệu cũ rồi nạp lại.
Sau khi import, chạy `python -m scripts.embed_verses` để tạo embedding cho semantic search.
"""

import json
import re
import sys
from pathlib import Path

from sqlalchemy import delete, insert, text

from app.database import Base, SessionLocal, engine
from app.models import Book, Verse

OLD_TESTAMENT_BOOKS = 39
BATCH_SIZE = 5000


def join_tokens(tokens: list[list[str]]) -> str:
    """Mỗi câu trong JSON là danh sách token [chữ, mã Strong?]; ghép lại thành câu hoàn chỉnh."""
    text = " ".join(token[0] for token in tokens)
    text = re.sub(r"\s+([,.;:?!)\]’—])", r"\1", text)  # bỏ khoảng trắng trước dấu câu
    text = re.sub(r"([(\[—])\s+", r"\1", text)  # bỏ khoảng trắng sau ( [ —
    text = re.sub(r"\s+-\s*", "-", text)  # cloven - footed -> cloven-footed
    return re.sub(r"\s{2,}", " ", text).strip()


def main(json_path: str) -> None:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    books, verses = [], []
    for position, (name, chapters) in enumerate(data["books"].items(), start=1):
        books.append(
            {
                "id": position,
                "name": name,
                "testament": "OT" if position <= OLD_TESTAMENT_BOOKS else "NT",
                "chapter_count": len(chapters),
            }
        )
        for chapter_no, chapter in enumerate(chapters, start=1):
            for verse_no, tokens in enumerate(chapter, start=1):
                verses.append(
                    {
                        "book_id": position,
                        "chapter": chapter_no,
                        "verse": verse_no,
                        "text": join_tokens(tokens),
                    }
                )

    with engine.begin() as conn:  # extension pgvector phải có trước khi tạo bảng
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    with SessionLocal() as db, db.begin():
        db.execute(delete(Verse))
        db.execute(delete(Book))
        db.execute(insert(Book), books)
        for i in range(0, len(verses), BATCH_SIZE):
            db.execute(insert(Verse), verses[i : i + BATCH_SIZE])

    print(f"Đã import {len(books)} sách, {len(verses)} câu ({data.get('versionName', '')}).")
    print("Bước tiếp theo: python -m scripts.embed_verses")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Cách dùng: python -m scripts.import_bible <đường dẫn tới ESV.json>")
    main(sys.argv[1])
