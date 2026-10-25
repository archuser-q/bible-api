import os

os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "bible_test")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

import search
from database import Base, SessionLocal, engine, init_db
from main import app
from models import Book, Note, Verse


def one_hot(i: int) -> list[float]:
    vector = [0.0] * 384
    vector[i] = 1.0
    return vector


def fake_embed_query(text: str) -> list[float]:
    text = text.lower()
    if "worry" in text or "anxious" in text:
        return one_hot(0)
    if "love" in text:
        return one_hot(1)
    return one_hot(9)


BOOKS = [
    Book(id=1, name="Genesis", testament="OT", chapter_count=50),
    Book(id=43, name="John", testament="NT", chapter_count=21),
    Book(id=50, name="Philippians", testament="NT", chapter_count=4),
]

VERSES = [
    (1, 1, 1, "In the beginning, God created the heavens and the earth.", 5),
    (1, 1, 2, "The earth was without form and void.", 6),
    (43, 3, 16, "For God so loved the world, that he gave his only Son.", 1),
    (43, 3, 17, "For God did not send his Son into the world to condemn the world.", 7),
    (50, 4, 5, "Let your reasonableness be known to everyone. The Lord is at hand;", 8),
    (50, 4, 6, "do not be anxious about anything, but in everything by prayer let your requests be made known to God.", 0),
    (50, 4, 7, "And the peace of God, which surpasses all understanding, will guard your hearts.", 2),
]


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        db.add_all(BOOKS)
        db.flush()
        db.add_all(
            Verse(book_id=b, chapter=c, verse=v, text=t, embedding=one_hot(dim))
            for b, c, v, t, dim in VERSES
        )
        db.commit()
    yield


@pytest.fixture(autouse=True)
def clean_notes_and_fake_model(monkeypatch):
    with SessionLocal() as db:
        db.execute(delete(Note))
        db.commit()
    monkeypatch.setattr(search, "embed_query", fake_embed_query)


@pytest.fixture
def client():
    return TestClient(app)
