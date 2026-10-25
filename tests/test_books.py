import pytest


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_books(client):
    books = client.get("/books").json()
    assert [b["name"] for b in books] == ["Genesis", "John", "Philippians"]


def test_get_chapter(client):
    response = client.get("/books/43/chapters/3")
    assert response.status_code == 200
    data = response.json()
    assert data["book"]["name"] == "John"
    assert [v["verse"] for v in data["verses"]] == [16, 17]


def test_get_verse(client):
    response = client.get("/books/43/chapters/3/verses/16")
    assert response.status_code == 200
    assert response.json()["text"].startswith("For God so loved the world")


@pytest.mark.parametrize(
    "url",
    [
        "/books/99/chapters/1",  # sách không tồn tại
        "/books/1/chapters/99",  # chương không tồn tại
        "/books/1/chapters/1/verses/99",  # câu không tồn tại
    ],
)
def test_not_found(client, url):
    assert client.get(url).status_code == 404


def test_invalid_id_type(client):
    assert client.get("/books/abc/chapters/1").status_code == 422
