def test_keyword_search_matches_word_forms(client):
    # "love" khớp cả "loved" nhờ PostgreSQL đưa từ về dạng gốc
    data = client.get("/search", params={"q": "love"}).json()
    assert data["total"] == 1
    assert data["results"][0]["book_name"] == "John"


def test_keyword_search_no_result(client):
    data = client.get("/search", params={"q": "xyzqwe"}).json()
    assert data == {"query": "xyzqwe", "total": 0, "results": []}


def test_keyword_search_validation(client):
    assert client.get("/search", params={"q": "a"}).status_code == 422


def test_semantic_search_finds_by_meaning(client):
    data = client.get("/search/semantic", params={"q": "do not worry", "limit": 3}).json()
    top = data["results"][0]
    assert (top["book_name"], top["chapter"], top["verse"]) == ("Philippians", 4, 6)
    assert top["score"] == 1.0
    assert len(data["results"]) == 3
