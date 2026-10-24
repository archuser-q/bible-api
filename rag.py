import logging
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from llm import LLMError, chat
from search import semantic_search

router = APIRouter(prefix="/ask", tags=["ask (RAG)"])
logger = logging.getLogger("uvicorn.error")  # in log ra cùng chỗ với log của server

SYSTEM_PROMPT = """You are a Bible study assistant.
Answer the user's question using ONLY the Bible verses provided in the context.

Rules:
- Cite the verses you use with their numbers in square brackets, e.g. [1] or [2][5].
- If the context does not contain enough information, say so honestly. Do not guess.
- Never invent verses or quote anything that is not in the context.
- Keep the answer short (at most about 150 words), plain text, no Markdown."""


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(8, ge=1, le=20) 


class Source(BaseModel):
    index: int
    book_id: int
    book_name: str
    chapter: int
    verse: int
    text: str


class AskResponse(BaseModel):
    answer: str
    cited: list[int]
    sources: list[Source]
    model: str
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None


@router.post("", response_model=AskResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)):
    started = time.time()

    # 1. Retrieval: tìm các câu gần nghĩa nhất (dùng lại hàm của /search/semantic)
    verses = semantic_search(q=body.question, limit=body.top_k, db=db)["results"]

    # 2. Augmented: đánh số các câu rồi đưa vào prompt
    context = "\n".join(
        f"[{i}] {v['book_name']} {v['chapter']}:{v['verse']} — {v['text']}"
        for i, v in enumerate(verses, start=1)
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {body.question}"},
    ]

    # 3. Generation: LLM viết câu trả lời
    try:
        answer, model, usage = chat(messages)
    except LLMError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    # Chỉ giữ các trích dẫn có thật (LLM có thể bịa ra [99])
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= len(verses)})

    latency_ms = int((time.time() - started) * 1000)
    logger.info("ask model=%s latency_ms=%d tokens=%s", model, latency_ms, usage)

    return {
        "answer": answer,
        "cited": cited,
        "sources": [{"index": i, **v} for i, v in enumerate(verses, start=1)],
        "model": model,
        "latency_ms": latency_ms,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
    }