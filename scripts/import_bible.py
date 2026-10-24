import json
import re
import sys

from database import Base, SessionLocal, engine, init_db
from models import Book, Verse


def join_words(words):
    # Mỗi câu trong file JSON là danh sách từ: [["In the"], ["beginning", "H7225"], ...]
    text = " ".join(w[0] for w in words)
    text = re.sub(r"\s+([,.;:?!)\]’—])", r"\1", text)  # bỏ dấu cách trước dấu câu
    text = re.sub(r"([(\[—])\s+", r"\1", text)  # bỏ dấu cách sau ( [ —
    text = re.sub(r"\s+-\s*", "-", text)  # "cloven - footed" -> "cloven-footed"
    return text.strip()


def main(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    Base.metadata.drop_all(engine, tables=[Verse.__table__, Book.__table__])
    init_db()

    with SessionLocal() as db:
        for book_id, (name, chapters) in enumerate(data["books"].items(), start=1):
            db.add(Book(
                id=book_id,
                name=name,
                testament="OT" if book_id <= 39 else "NT",
                chapter_count=len(chapters),
            ))
            for chapter_no, verses in enumerate(chapters, start=1):
                for verse_no, words in enumerate(verses, start=1):
                    db.add(Verse(book_id=book_id, chapter=chapter_no, verse=verse_no, text=join_words(words)))
        db.commit()

    print("Import xong")


if __name__ == "__main__":
    main(sys.argv[1])