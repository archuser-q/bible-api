from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book, Verse
from app.schemas import BookOut, ChapterOut, VerseOut

router = APIRouter(prefix="/books", tags=["books"])


def _get_book_or_404(db: Session, book_id: int) -> Book:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")
    return book


@router.get("", response_model=list[BookOut])
def list_books(testament: str | None = None, db: Session = Depends(get_db)):
    """Danh sách 66 sách. Lọc theo testament=OT hoặc NT nếu cần."""
    stmt = select(Book).order_by(Book.id)
    if testament:
        stmt = stmt.where(Book.testament == testament.upper())
    return db.scalars(stmt).all()


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return _get_book_or_404(db, book_id)


@router.get("/{book_id}/chapters/{chapter}", response_model=ChapterOut)
def get_chapter(book_id: int, chapter: int, db: Session = Depends(get_db)):
    book = _get_book_or_404(db, book_id)
    if not 1 <= chapter <= book.chapter_count:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương")

    verses = db.scalars(
        select(Verse)
        .where(Verse.book_id == book_id, Verse.chapter == chapter)
        .order_by(Verse.verse)
    ).all()
    return ChapterOut(book=book, chapter=chapter, verses=verses)


@router.get("/{book_id}/chapters/{chapter}/verses/{verse}", response_model=VerseOut)
def get_verse(book_id: int, chapter: int, verse: int, db: Session = Depends(get_db)):
    row = db.scalar(
        select(Verse).where(
            Verse.book_id == book_id, Verse.chapter == chapter, Verse.verse == verse
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu")
    return row
