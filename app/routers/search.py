from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.embeddings import embed_query
from app.models import Book, Verse
from app.schemas import SearchHit, SearchResult

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResult)
def search_verses(
    q: str = Query(..., min_length=2, description='Từ khóa, ví dụ: love, "living water", faith -works'),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Full-text search bằng PostgreSQL (tsvector + GIN index), xếp theo độ liên quan."""
    tsquery = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank(Verse.search_vector, tsquery).label("rank")

    rows = db.execute(
        select(Verse.book_id, Book.name, Verse.chapter, Verse.verse, Verse.text, rank)
        .join(Book, Book.id == Verse.book_id)
        .where(Verse.search_vector.op("@@")(tsquery))
        .order_by(rank.desc(), Verse.id)
        .limit(limit)
        .offset(offset)
    ).all()

    total = db.scalar(
        select(func.count()).select_from(Verse).where(Verse.search_vector.op("@@")(tsquery))
    )

    hits = [
        SearchHit(book_id=b_id, book_name=name, chapter=ch, verse=v, text=t, rank=r)
        for b_id, name, ch, v, t, r in rows
    ]
    return SearchResult(query=q, count=total or 0, results=hits)


@router.get("/semantic", response_model=SearchResult)
def semantic_search(
    q: str = Query(..., min_length=2, description="Câu hỏi tự nhiên, ví dụ: verses about anxiety"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Tìm theo ý nghĩa: so khoảng cách cosine giữa vector câu hỏi và vector từng câu (pgvector, HNSW).

    `rank` ở đây là độ tương đồng (0–1, càng cao càng giống).
    """
    query_vector = embed_query(q)
    distance = Verse.embedding.cosine_distance(query_vector).label("distance")

    rows = db.execute(
        select(Verse.book_id, Book.name, Verse.chapter, Verse.verse, Verse.text, distance)
        .join(Book, Book.id == Verse.book_id)
        .where(Verse.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    ).all()

    if not rows:
        raise HTTPException(
            status_code=503,
            detail="Chưa có embedding. Hãy chạy: python -m scripts.embed_verses",
        )

    hits = [
        SearchHit(book_id=b_id, book_name=name, chapter=ch, verse=v, text=t, rank=round(1 - d, 4))
        for b_id, name, ch, v, t, d in rows
    ]
    return SearchResult(query=q, count=len(hits), results=hits)
