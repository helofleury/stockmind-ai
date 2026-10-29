
from datetime import date

from app.inventory import analyze_inventory


def test_identifies_low_stock():
    items = [
        {
            "name": "Luvas",
            "quantity": 5,
            "minimum_quantity": 10,
            "expiration_date": "2027-12-31",
        }
    ]

    result = analyze_inventory(items, today=date(2026, 10, 28))

    assert "LOW_STOCK" in result[0]["risks"]


def test_identifies_expiring_soon():
    items = [
        {
            "name": "Seringas",
            "quantity": 100,
            "minimum_quantity": 20,
            "expiration_date": "2026-11-10",
        }
    ]

    result = analyze_inventory(items, today=date(2026, 10, 28))

    assert "EXPIRING_SOON" in result[0]["risks"]


def test_identifies_expired_items():
    items = [
        {
            "name": "Material fictício",
            "quantity": 10,
            "minimum_quantity": 5,
            "expiration_date": "2026-10-01",
        }
    ]

    result = analyze_inventory(items, today=date(2026, 10, 28))

    assert "EXPIRED" in result[0]["risks"]


def test_identifies_overstock():
    items = [
        {
            "name": "Máscaras",
            "quantity": 100,
            "minimum_quantity": 20,
            "expiration_date": "2027-12-31",
        }
    ]

    result = analyze_inventory(items, today=date(2026, 10, 28))

    assert "OVERSTOCK" in result[0]["risks"]
