
import json

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_stockmind.db"
    test_json = tmp_path / "inventory.json"

    test_items = [
        {
            "id": 1,
            "name": "Produto de teste",
            "quantity": 50,
            "minimum_quantity": 10,
            "expiration_date": "2028-12-31",
        }
    ]

    test_json.write_text(
        json.dumps(test_items),
        encoding="utf-8",
    )

    monkeypatch.setattr(database, "DATABASE_FILE", test_db)
    monkeypatch.setattr(database, "INVENTORY_FILE", test_json)

    database.initialize_database()

    with TestClient(app) as test_client:
        yield test_client


def test_create_inventory_item(client):
    response = client.post(
        "/inventory",
        json={
            "name": "Novo produto",
            "quantity": 20,
            "minimum_quantity": 5,
            "expiration_date": "2028-12-31",
        },
    )

    assert response.status_code == 201
    assert response.json()["item"]["name"] == "Novo produto"


def test_update_inventory_quantity(client):
    response = client.patch(
        "/inventory/1",
        json={"quantity": 25},
    )

    assert response.status_code == 200
    assert response.json()["item"]["quantity"] == 25


def test_register_stock_entry(client):
    response = client.post(
        "/inventory/1/movements",
        json={
            "movement_type": "IN",
            "quantity": 10,
            "reason": "Reposição de teste",
        },
    )

    assert response.status_code == 201
    assert response.json()["movement"]["balance_after"] == 60

    inventory = client.get("/inventory").json()
    assert inventory[0]["quantity"] == 60


def test_register_stock_exit(client):
    response = client.post(
        "/inventory/1/movements",
        json={
            "movement_type": "OUT",
            "quantity": 10,
            "reason": "Saída de teste",
        },
    )

    assert response.status_code == 201
    assert response.json()["movement"]["balance_after"] == 40


def test_reject_exit_above_available_stock(client):
    response = client.post(
        "/inventory/1/movements",
        json={
            "movement_type": "OUT",
            "quantity": 100,
            "reason": "Teste de saldo insuficiente",
        },
    )

    assert response.status_code == 400

    inventory = client.get("/inventory").json()
    assert inventory[0]["quantity"] == 50


def test_movement_is_saved_in_history(client):
    client.post(
        "/inventory/1/movements",
        json={
            "movement_type": "IN",
            "quantity": 5,
            "reason": "Teste de histórico",
        },
    )

    response = client.get("/movements")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["reason"] == "Teste de histórico"


def test_delete_product_without_movements(client):
    response = client.delete("/inventory/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_prevent_delete_product_with_movements(client):
    client.post(
        "/inventory/1/movements",
        json={
            "movement_type": "IN",
            "quantity": 5,
            "reason": "Preservar histórico",
        },
    )

    response = client.delete("/inventory/1")

    assert response.status_code == 409


def test_inventory_summary(client):
    response = client.get("/inventory/summary")

    assert response.status_code == 200

    summary = response.json()
    assert summary["total_products"] == 1
    assert summary["total_units"] == 50
