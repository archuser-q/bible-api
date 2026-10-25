from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Note, Verse
from security import require_api_key

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(require_api_key)])

class NoteCreate(BaseModel):
    book_id: int
    chapter: int = Field(ge=1)
    verse: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=2000)


class NoteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class NoteOut(BaseModel):
    id: int
    book_id: int
    chapter: int
    verse: int
    content: str
    created_at: datetime
    updated_at: datetime


def get_note_or_404(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ghi chú")
    return note



@router.post("", response_model=NoteOut, status_code=201)
def create_note(body: NoteCreate, db: Session = Depends(get_db)):
    exists = db.scalar(
        select(Verse.id).where(
            Verse.book_id == body.book_id, Verse.chapter == body.chapter, Verse.verse == body.verse
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu")

    note = Note(**body.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=list[NoteOut])
def list_notes(book_id: int | None = None, chapter: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Note).order_by(Note.created_at.desc())
    if book_id is not None:
        stmt = stmt.where(Note.book_id == book_id)
    if chapter is not None:
        stmt = stmt.where(Note.chapter == chapter)
    return db.scalars(stmt).all()


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: int, db: Session = Depends(get_db)):
    return get_note_or_404(db, note_id)


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db)):
    note = get_note_or_404(db, note_id)
    note.content = body.content
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = get_note_or_404(db, note_id)
    db.delete(note)
    db.commit()