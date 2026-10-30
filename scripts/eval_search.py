"""Đo chất lượng tìm kiếm trên bộ câu hỏi mẫu eval/queries.json.

Cách chạy:
    python -m scripts.eval_search            # bảng tổng hợp
    python -m scripts.eval_search --verbose  # in thêm các câu hỏi bị trượt

Chỉ số (lấy top 10 kết quả):
    Hit@5     % câu hỏi có ít nhất 1 câu đúng trong 5 kết quả đầu
    Recall@10 trung bình tỉ lệ câu đúng tìm được trong 10 kết quả đầu
    MRR       trung bình của 1/vị trí câu đúng đầu tiên (đúng ở vị trí 1 -> 1.0, vị trí 2 -> 0.5...)
"""

import json
import sys
from pathlib import Path

from database import SessionLocal
from models import Book, Verse
from search import search_verses, semantic_search

K = 10
QUERIES_FILE = Path("eval/queries.json")


def keyword(db, query):
    return search_verses(q=query, limit=K, offset=0, db=db)["results"]


def semantic(db, query):
    return semantic_search(q=query, limit=K, db=db)["results"]


METHODS = {"keyword": keyword, "semantic": semantic}


def check_references(db, queries):
    """Báo lỗi ngay nếu bộ dữ liệu ghi sai tên sách / chương / câu."""
    for item in queries:
        for ref in item["relevant"]:
            book, chapter_verse = ref.rsplit(" ", 1)
            chapter, verse = map(int, chapter_verse.split(":"))
            exists = (
                db.query(Verse.id)
                .join(Book, Book.id == Verse.book_id)
                .filter(Book.name == book, Verse.chapter == chapter, Verse.verse == verse)
                .first()
            )
            if exists is None:
                sys.exit(f"Tham chiếu không tồn tại: {ref} (câu hỏi: {item['query']})")


def score(results, relevant):
    """Trả về (hit@5, recall@10, reciprocal rank) cho 1 câu hỏi."""
    found = [f"{r['book_name']} {r['chapter']}:{r['verse']}" for r in results]
    relevant = set(relevant)

    hit5 = any(ref in relevant for ref in found[:5])
    recall = len(relevant & set(found)) / len(relevant)
    rank = next((i for i, ref in enumerate(found, start=1) if ref in relevant), None)
    return hit5, recall, (1 / rank if rank else 0.0)


def main(verbose):
    queries = json.loads(QUERIES_FILE.read_text())

    with SessionLocal() as db:
        check_references(db, queries)

        print(f"{len(queries)} câu hỏi, top {K} kết quả\n")
        print(f"{'Phương pháp':<10} {'Nhóm':<8} {'Hit@5':>7} {'Recall@10':>10} {'MRR':>6}")

        for name, search in METHODS.items():
            rows = []
            for item in queries:
                hit5, recall, rr = score(search(db, item["query"]), item["relevant"])
                rows.append((item, hit5, recall, rr))

            # In kết quả cho tất cả, rồi tách theo nhóm câu hỏi
            for group in ("all", "quote", "meaning"):
                part = [r for r in rows if group == "all" or r[0]["type"] == group]
                n = len(part)
                print(
                    f"{name:<10} {group:<8} "
                    f"{sum(r[1] for r in part) / n:>7.0%} "
                    f"{sum(r[2] for r in part) / n:>10.0%} "
                    f"{sum(r[3] for r in part) / n:>6.2f}"
                )

            if verbose:
                misses = [r[0]["query"] for r in rows if not r[1]]
                print(f"  -> {name} trượt Hit@5 ({len(misses)}): {misses}")


if __name__ == "__main__":
    main(verbose="--verbose" in sys.argv)
