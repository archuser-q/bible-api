from pydantic import BaseModel, ConfigDict


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    testament: str
    chapter_count: int


class VerseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verse: int
    text: str


class ChapterOut(BaseModel):
    book: BookOut
    chapter: int
    verses: list[VerseOut]


class SearchHit(BaseModel):
    book_id: int
    book_name: str
    chapter: int
    verse: int
    text: str
    rank: float


class SearchResult(BaseModel):
    query: str
    count: int
    results: list[SearchHit]
