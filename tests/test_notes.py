NOTE = {"book_id": 43, "chapter": 3, "verse": 16, "content": "Câu yêu thích"}


def test_note_crud_flow(client):
    # Tạo
    response = client.post("/notes", json=NOTE)
    assert response.status_code == 201
    note = response.json()
    assert note["content"] == "Câu yêu thích"

    # Đọc
    assert client.get(f"/notes/{note['id']}").json()["content"] == "Câu yêu thích"

    # Sửa
    response = client.patch(f"/notes/{note['id']}", json={"content": "Đã sửa"})
    assert response.status_code == 200
    assert response.json()["content"] == "Đã sửa"

    # Xóa
    assert client.delete(f"/notes/{note['id']}").status_code == 204
    assert client.get(f"/notes/{note['id']}").status_code == 404


def test_list_notes_filter_by_book(client):
    client.post("/notes", json=NOTE)
    client.post("/notes", json={**NOTE, "book_id": 1, "chapter": 1, "verse": 1})

    assert len(client.get("/notes").json()) == 2
    assert len(client.get("/notes", params={"book_id": 43}).json()) == 1


def test_cannot_note_missing_verse(client):
    response = client.post("/notes", json={**NOTE, "verse": 999})
    assert response.status_code == 404


def test_note_validation(client):
    assert client.post("/notes", json={**NOTE, "content": ""}).status_code == 422
    assert client.post("/notes", json={**NOTE, "chapter": 0}).status_code == 422


def test_update_missing_note(client):
    assert client.patch("/notes/999999", json={"content": "x"}).status_code == 404
