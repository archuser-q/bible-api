from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

import notes
from database import Base, engine, get_db
from models import Book, Verse

Base.metadata.create_all(engine)

app = FastAPI(title="Bible API")
app.include_router(notes.router)

class BookOut(BaseModel):
    id: int
    name: str
    testament: str
    chapter_count: int


class VerseOut(BaseModel):
    verse: int
    text: str


class ChapterOut(BaseModel):
    book: BookOut
    chapter: int
    verses: list[VerseOut]

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/books", response_model=list[BookOut])
def list_books(db: Session = Depends(get_db)):
    return db.scalars(select(Book).order_by(Book.id)).all()


@app.get("/books/{book_id}/chapters/{chapter}", response_model=ChapterOut)
def get_chapter(book_id: int, chapter: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")

    verses = db.scalars(
        select(Verse)
        .where(Verse.book_id == book_id, Verse.chapter == chapter)
        .order_by(Verse.verse)
    ).all()
    if not verses:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương")

    return {"book": book, "chapter": chapter, "verses": verses}


@app.get("/books/{book_id}/chapters/{chapter}/verses/{verse}", response_model=VerseOut)
def get_verse(book_id: int, chapter: int, verse: int, db: Session = Depends(get_db)):
    row = db.scalar(
        select(Verse).where(Verse.book_id == book_id, Verse.chapter == chapter, Verse.verse == verse)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu")
    return row