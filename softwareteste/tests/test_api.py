from app import create_app


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_products_initial_contract(client):
    response = client.get("/products")
    assert response.status_code == 200
    assert response.json["total"] == 12
    assert [item["id"] for item in response.json["items"]] == list(range(1, 13))
    assert response.json["items"][0] == {"id": 1, "name": "Produto 01", "price_cents": 1000}


def test_create_valid_user(client):
    payload = {"name": "Ana", "email": "ana@example.com", "age": 25}
    response = client.post("/users", json=payload)
    assert response.status_code == 201
    assert response.json == {"id": 1, **payload}
    response = client.post("/users", json={**payload, "email": "outra@example.com"})
    assert response.json["id"] == 2


def test_app_instances_do_not_share_state(client):
    client.post("/users", json={"name": "Ana", "email": "a@example.com", "age": 25})
    other = create_app({"TESTING": True}).test_client()
    response = other.post("/users", json={"name": "Bia", "email": "b@example.com", "age": 30})
    assert response.json["id"] == 1


def test_unknown_route_is_json(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert "error" in response.json


def test_wrong_method(client):
    assert client.post("/products").status_code == 405


def test_non_object_json(client):
    assert client.post("/users", json=[]).status_code == 400


def test_malformed_json(client):
    response = client.post("/users", data="{", content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.json
