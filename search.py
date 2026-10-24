from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from embeddings import embed_query
from models import Book, Verse

router = APIRouter(prefix="/search", tags=["search"])


class SearchHit(BaseModel):
    book_id: int
    book_name: str
    chapter: int
    verse: int
    text: str
    score: float | None = None


class SearchResult(BaseModel):
    query: str
    total: int
    results: list[SearchHit]


@router.get("", response_model=SearchResult)
def search_verses(
    q: str = Query(min_length=2, description='vd: love, "living water", faith -works'),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = func.websearch_to_tsquery("english", q)
    matches = Verse.search_vector.op("@@")(query) 
    rank = func.ts_rank(Verse.search_vector, query)

    rows = db.execute(
        select(Verse.book_id, Book.name, Verse.chapter, Verse.verse, Verse.text)
        .join(Book, Book.id == Verse.book_id)
        .where(matches)
        .order_by(rank.desc(), Verse.id)
        .limit(limit)
        .offset(offset)
    ).all()

    total = db.scalar(select(func.count()).select_from(Verse).where(matches))

    return {
        "query": q,
        "total": total,
        "results": [
            {"book_id": b, "book_name": n, "chapter": c, "verse": v, "text": t}
            for b, n, c, v, t in rows
        ],
    }

@router.get("/semantic", response_model=SearchResult)
def semantic_search(
    q: str = Query(min_length=2, description="vd: verses about anxiety"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    query_vector = embed_query(q)  # đổi câu hỏi thành vector
    distance = Verse.embedding.cosine_distance(query_vector)  # khoảng cách: càng nhỏ càng giống

    rows = db.execute(
        select(Verse.book_id, Book.name, Verse.chapter, Verse.verse, Verse.text, distance)
        .join(Book, Book.id == Verse.book_id)
        .where(Verse.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    ).all()

    if not rows:
        raise HTTPException(status_code=503, detail="Chưa có embedding, hãy chạy: python -m scripts.embed_verses")

    return {
        "query": q,
        "total": len(rows),
        "results": [
            {"book_id": b, "book_name": n, "chapter": c, "verse": v, "text": t, "score": round(1 - d, 4)}
            for b, n, c, v, t, d in rows
        ],
    }