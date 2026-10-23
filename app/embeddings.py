import threading

from app.config import settings

EMBEDDING_DIM = 384

QUERY_PROMPT = "Represent this sentence for searching relevant passages: "

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                # import ở đây để API khởi động nhanh, không phải nạp torch ngay
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(settings.embedding_model, device="cpu")
    return _model


def embed_query(text: str) -> list[float]:
    vector = get_model().encode(text, prompt=QUERY_PROMPT, normalize_embeddings=True)
    return vector.tolist()


def embed_passages(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    vectors = get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()
