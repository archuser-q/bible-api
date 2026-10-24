import os

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None


def get_model():
    global _model
    if _model is None:
        _model = TextEmbedding(
            MODEL_NAME,
            cache_dir="data/fastembed",
            threads=int(os.getenv("EMBED_THREADS", "2")),
        )
    return _model


def embed_query(text):
    vector = next(get_model().embed(QUERY_PREFIX + text))
    return vector.tolist()


def embed_passages(texts):
    return [vector.tolist() for vector in get_model().embed(texts, batch_size=32)]