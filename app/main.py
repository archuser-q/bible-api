import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.embeddings import get_model
from app.routers import books, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=get_model, daemon=True).start()
    yield


app = FastAPI(title="Bible API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(search.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
