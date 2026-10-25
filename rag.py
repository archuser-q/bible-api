import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from llm import LLMError, chat
from models import Verse
from search import semantic_search
from security import rate_limit, require_api_key

router = APIRouter(prefix="/ask", tags=["ask (RAG)"], dependencies=[Depends(require_api_key), Depends(rate_limit)])
logger = logging.getLogger("uvicorn.error")  # in log ra cùng chỗ với log của server

SYSTEM_PROMPT = """You are a thoughtful Bible teacher.
The user asks a question; you receive Bible passages related to it in the context.

Write a deep, well-reasoned answer, not a list of quotes:
- Start with a short, direct answer to the question.
- Then explain the main ideas: what the passages mean, why they say it,
  and how different passages connect to or balance each other.
- Add relevant historical or literary background when it helps understanding.
- End with how this applies to everyday life today.
- Build mainly on the passages in the context. Mention references naturally,
  e.g. (Philippians 4:6), but never quote words that are not in the context.
- If the passages do not really answer the question, say so honestly.
- About 250–400 words, simple Markdown (short headings or paragraphs).
- Reply in the same language as the question."""


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(8, ge=1, le=20)  # số câu tìm được (mỗi câu sẽ được mở rộng thành 1 đoạn)


class AskResponse(BaseModel):
    answer: str
    model: str
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None


def build_passages(db: Session, hits: list[dict], radius: int = 2) -> list[str]:
    """Mở rộng mỗi câu tìm được thành 1 đoạn (thêm 2 câu trước và 2 câu sau).

    Một câu đứng một mình dễ bị hiểu sai; có câu xung quanh thì LLM hiểu đúng ngữ cảnh hơn.
    Các câu gần nhau trong cùng một chương được gộp thành một đoạn để không lặp lại.
    """
    # Gom khoảng [đầu, cuối] theo từng chương, giữ thứ tự: chương liên quan nhất đứng trước
    chapters: dict[tuple[str, int, int], list[list[int]]] = {}
    for hit in hits:
        key = (hit["book_name"], hit["book_id"], hit["chapter"])
        chapters.setdefault(key, []).append([max(1, hit["verse"] - radius), hit["verse"] + radius])

    passages = []
    for (book_name, book_id, chapter), spans in chapters.items():
        # Gộp các khoảng chồng lên nhau: [3,7] + [6,10] -> [3,10]
        spans.sort()
        merged = [spans[0]]
        for start, end in spans[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])

        for start, end in merged:
            rows = db.execute(
                select(Verse.verse, Verse.text)
                .where(Verse.book_id == book_id, Verse.chapter == chapter)
                .where(Verse.verse.between(start, end))
                .order_by(Verse.verse)
            ).all()
            if rows:
                body = "\n".join(f"{verse} {text}" for verse, text in rows)
                passages.append(f"{book_name} {chapter}:{rows[0][0]}-{rows[-1][0]}\n{body}")
    return passages


@router.post("", response_model=AskResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)):
    started = time.time()

    # 1. Retrieval: tìm các câu gần nghĩa nhất, rồi mở rộng thành các đoạn có ngữ cảnh
    hits = semantic_search(q=body.question, limit=body.top_k, db=db)["results"]
    passages = build_passages(db, hits)

    # 2. Augmented: đưa các đoạn vào prompt
    context = "\n\n".join(passages)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {body.question}"},
    ]

    # 3. Generation: câu trả lời dài hơn -> cho nhiều token hơn
    try:
        answer, model, usage = chat(messages, max_tokens=1500, temperature=0.4)
    except LLMError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    latency_ms = int((time.time() - started) * 1000)
    logger.info("ask model=%s latency_ms=%d passages=%d tokens=%s", model, latency_ms, len(passages), usage)

    return {
        "answer": answer,
        "model": model,
        "latency_ms": latency_ms,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
    }