import logging
import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from openai import APIError
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from database import SessionLocal
from llm import MODELS, LLMError
from models import Book, Note, Verse
from search import semantic_search
from security import rate_limit, require_api_key

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_api_key), Depends(rate_limit)])
logger = logging.getLogger("uvicorn.error")

SYSTEM_PROMPT = """You are a Bible study assistant with tools.

- To answer questions about a topic, call search_verses first, then answer using those verses.
- To read a specific passage, call get_passage.
- Only call save_note when the user clearly asks to save or remember something.
- Always cite references like (John 3:16). Never invent verses.
- Keep answers short, plain text."""


# ---------------- Tools: các hàm agent được phép gọi ----------------

def find_book(db, name: str) -> Book | None:
    """Tìm sách theo tên gần đúng: "john" -> John, "1 samuel" -> I Samuel."""
    name = name.strip().lower()
    for number, roman in (("1 ", "i "), ("2 ", "ii "), ("3 ", "iii ")):
        if name.startswith(number):
            name = roman + name[len(number):]
    return db.scalar(
        select(Book).where(func.lower(Book.name).startswith(name)).order_by(Book.id)
    )


@tool
def search_verses(query: str) -> str:
    """Find Bible verses whose meaning matches the query. Use for topics and questions."""
    with SessionLocal() as db:
        results = semantic_search(q=query, limit=6, db=db)["results"]
    return "\n".join(
        f"{r['book_name']} {r['chapter']}:{r['verse']} — {r['text']}" for r in results
    )


@tool
def get_passage(book: str, chapter: int, start_verse: int = 1, end_verse: int = 0) -> str:
    """Read verses of a chapter, e.g. book="John", chapter=3, start_verse=16, end_verse=18.
    end_verse=0 means read to the end of the chapter (max 30 verses)."""
    with SessionLocal() as db:
        found = find_book(db, book)
        if found is None:
            return f"Book not found: {book}"
        stmt = select(Verse).where(
            Verse.book_id == found.id, Verse.chapter == chapter, Verse.verse >= start_verse
        )
        if end_verse:
            stmt = stmt.where(Verse.verse <= end_verse)
        verses = db.scalars(stmt.order_by(Verse.verse).limit(30)).all()
    if not verses:
        return f"No verses found in {found.name} {chapter}"
    return "\n".join(f"{found.name} {chapter}:{v.verse} — {v.text}" for v in verses)


@tool
def save_note(book: str, chapter: int, verse: int, content: str) -> str:
    """Save the user's personal note on a verse."""
    with SessionLocal() as db:
        found = find_book(db, book)
        if found is None:
            return f"Book not found: {book}"
        note = Note(book_id=found.id, chapter=chapter, verse=verse, content=content)
        db.add(note)
        db.commit()
        return f"Saved note #{note.id} on {found.name} {chapter}:{verse}"


@tool
def list_notes() -> str:
    """List the user's 20 most recent notes."""
    with SessionLocal() as db:
        rows = db.execute(
            select(Note, Book.name)
            .join(Book, Book.id == Note.book_id)
            .order_by(Note.created_at.desc())
            .limit(20)
        ).all()
    if not rows:
        return "The user has no notes yet."
    return "\n".join(f"{name} {n.chapter}:{n.verse} — {n.content}" for n, name in rows)


TOOLS = [search_verses, get_passage, save_note, list_notes]


# ---------------- LLM ----------------

_llm = None


def get_llm():
    """LLM đã được "gắn" danh sách tool, có model dự phòng."""
    global _llm
    if _llm is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise LLMError("Chưa có OPENROUTER_API_KEY trong file .env")
        models = [
            ChatOpenAI(
                model=name,
                api_key=api_key,
                base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
                temperature=0.2,
                timeout=60,
                max_retries=0,
            ).bind_tools(TOOLS)
            for name in MODELS
        ]
        _llm = models[0].with_fallbacks(models[1:])
    return _llm


# ---------------- Graph: agent <-> tools ----------------

def agent_node(state: MessagesState):
    # Chỉ gửi 20 tin nhắn gần nhất để tiết kiệm token (bắt đầu từ một câu của người dùng)
    history = state["messages"][-20:]
    while history and not isinstance(history[0], HumanMessage):
        history = history[1:]

    response = get_llm().invoke([SystemMessage(SYSTEM_PROMPT), *history])
    return {"messages": [response]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent_node)  # LLM suy nghĩ: trả lời luôn hay gọi tool?
builder.add_node("tools", ToolNode(TOOLS))  # chạy tool LLM đã chọn
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)  # có gọi tool -> "tools", không -> kết thúc
builder.add_edge("tools", "agent")  # có kết quả tool -> quay lại cho LLM đọc
graph = builder.compile(checkpointer=InMemorySaver())  # memory: lưu hội thoại theo thread_id


# ---------------- API ----------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    thread_id: str | None = None  # gửi lại thread_id cũ để agent nhớ hội thoại


class Step(BaseModel):
    tool: str
    args: dict


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    latency_ms: int


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    started = time.time()
    thread_id = body.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 12}

    old_count = len(graph.get_state(config).values.get("messages", []))
    try:
        result = graph.invoke({"messages": [HumanMessage(body.message)]}, config)
    except GraphRecursionError as error:
        raise HTTPException(status_code=500, detail="Agent dùng quá nhiều bước") from error
    except (LLMError, APIError) as error:
        raise HTTPException(status_code=503, detail=f"Không gọi được LLM: {error}") from error

    new_messages = result["messages"][old_count:]
    steps = [
        {"tool": call["name"], "args": call["args"]}
        for message in new_messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]
    reply = result["messages"][-1].content

    latency_ms = int((time.time() - started) * 1000)
    logger.info("agent thread=%s steps=%s latency_ms=%d", thread_id, [s["tool"] for s in steps], latency_ms)

    return {"thread_id": thread_id, "reply": reply, "steps": steps, "latency_ms": latency_ms}