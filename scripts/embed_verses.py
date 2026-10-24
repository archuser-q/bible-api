import time

from sqlalchemy import select, text

from database import SessionLocal, engine
from embeddings import embed_passages
from models import Verse

BATCH_SIZE = 64


def main():
    with SessionLocal() as db:
        todo = db.execute(select(Verse.id, Verse.text).where(Verse.embedding.is_(None)).order_by(Verse.id)).all()
    print(f"Cần xử lý {len(todo)} câu")

    started = time.time()
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        vectors = embed_passages([row.text for row in batch])

        with SessionLocal() as db: 
            for row, vector in zip(batch, vectors):
                db.get(Verse, row.id).embedding = vector
            db.commit()

        done = i + len(batch)
        print(f"{done}/{len(todo)} — {done / (time.time() - started):.0f} câu/giây", flush=True)

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_verses_embedding ON verses USING hnsw (embedding vector_cosine_ops)"
        ))
    print("Xong")


if __name__ == "__main__":
    main()