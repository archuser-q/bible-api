# Bible API

Backend cho app đọc Kinh Thánh: **FastAPI + PostgreSQL + pgvector**, có full-text search và semantic search (tìm theo ý nghĩa).

## Chạy bằng Docker

```bash
# 1. Lấy dữ liệu
git clone --depth 1 https://github.com/lguenth/mdbible.git data/mdbible

# 2. Bật database + API (lần build đầu tải PyTorch CPU, mất vài phút)
docker compose up -d --build

# 3. Import dữ liệu (chỉ cần chạy 1 lần)
docker compose run --rm api python -m scripts.import_bible data/mdbible/json/ESV.json

# 4. Tạo embedding cho semantic search (chỉ cần chạy 1 lần, vài phút trên CPU)
docker compose run --rm api python -m scripts.embed_verses
```

Mở http://localhost:8000/docs để xem và thử API (Swagger).

### Nâng cấp từ bản cũ (đã import dữ liệu rồi)

Không cần import lại, chỉ cần build lại và tạo embedding:

```bash
docker compose down
docker compose up -d --build
docker compose run --rm api python -m scripts.embed_verses
```

## Chạy không cần Docker cho API

```bash
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # torch bản CPU, nhẹ
pip install -r requirements.txt
cp .env.example .env
python -m scripts.import_bible data/mdbible/json/ESV.json
python -m scripts.embed_verses
uvicorn app.main:app --reload
```

## API

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Kiểm tra server |
| GET | `/books?testament=OT\|NT` | Danh sách sách |
| GET | `/books/{book_id}` | Thông tin 1 sách |
| GET | `/books/{book_id}/chapters/{chapter}` | Toàn bộ câu trong 1 chương |
| GET | `/books/{book_id}/chapters/{chapter}/verses/{verse}` | 1 câu |
| GET | `/search?q=...&limit=20&offset=0` | Tìm kiếm full-text (từ khóa) |
| GET | `/search/semantic?q=...&limit=10` | Tìm theo ý nghĩa (semantic search) |

Ví dụ: `/books/43/chapters/3/verses/16` → Giăng 3:16.

Cú pháp tìm từ khóa: `love`, `"living water"` (cụm chính xác), `faith -works` (loại trừ từ).

Tìm theo ý nghĩa: gõ câu tự nhiên, ví dụ `verses about anxiety`, `God takes care of me when I am afraid`.
`rank` trong kết quả là độ tương đồng (0–1, càng cao càng giống).

## Semantic search hoạt động thế nào

1. `scripts/embed_verses.py` đưa từng câu qua mô hình `BAAI/bge-small-en-v1.5` → vector 384 chiều, lưu vào cột `verses.embedding` (kiểu `vector` của pgvector), rồi tạo index HNSW.
2. Khi tìm kiếm, câu hỏi cũng được đổi thành vector, PostgreSQL trả về các câu có khoảng cách cosine gần nhất (`ORDER BY embedding <=> query LIMIT k`).

Đổi mô hình: đặt biến môi trường `EMBEDDING_MODEL` (mô hình phải ra vector 384 chiều), rồi chạy `python -m scripts.embed_verses --all`.

## Cấu trúc

```
app/
  main.py          # khởi tạo FastAPI, đăng ký router
  config.py        # đọc DATABASE_URL, EMBEDDING_MODEL từ env
  database.py      # engine, session, get_db
  embeddings.py    # nạp mô hình, tạo vector cho câu hỏi / câu Kinh Thánh
  models.py        # bảng books, verses (+ tsvector/GIN, vector/HNSW)
  schemas.py       # Pydantic response models
  routers/
    books.py       # đọc sách / chương / câu
    search.py      # full-text search + semantic search
scripts/
  import_bible.py  # nạp JSON vào PostgreSQL
  embed_verses.py  # tạo embedding cho toàn bộ câu
```

## Lưu ý

Bản ESV có bản quyền (Crossway). Dùng cho học tập và portfolio là ổn; nếu phát hành app thì nên đổi sang bản phạm vi công cộng (Kinh Thánh Việt 1925, KJV, WEB).
