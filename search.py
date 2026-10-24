from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models import Book, Verse

router = APIRouter(prefix="/search", tags=["search"])


class SearchHit(BaseModel):
    book_id: int
    book_name: str
    chapter: int
    verse: int
    text: str


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