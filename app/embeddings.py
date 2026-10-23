"""Tạo embedding (vector) cho câu Kinh Thánh và câu hỏi tìm kiếm.

Mô hình chỉ được nạp vào RAM ở lần dùng đầu tiên (lazy), nạp một lần rồi dùng lại.
"""

import threading

from app.config import settings

EMBEDDING_DIM = 384

# bge-small-en-v1.5 khuyên thêm câu này trước CÂU HỎI (không thêm vào câu Kinh Thánh)
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
