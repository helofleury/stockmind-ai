
from datetime import date
from typing import Any


def analyze_inventory(
    items: list[dict[str, Any]],
    today: date | None = None,
) -> list[dict[str, Any]]:
    """
    Analisa dados fictícios de estoque e identifica riscos operacionais.

    Cada item deve conter:
    name, quantity, minimum_quantity, expiration_date.
    """
    reference_date = today or date.today()
    results = []

    for item in items:
        quantity = item["quantity"]
        minimum_quantity = item["minimum_quantity"]
        expiration_date = date.fromisoformat(item["expiration_date"])

        days_until_expiration = (expiration_date - reference_date).days
        risks = []

        if quantity <= minimum_quantity:
            risks.append("LOW_STOCK")

        if 0 <= days_until_expiration <= 30:
            risks.append("EXPIRING_SOON")
        elif days_until_expiration < 0:
            risks.append("EXPIRED")

        if quantity > minimum_quantity * 3:
            risks.append("OVERSTOCK")

        results.append(
            {
                "name": item["name"],
                "quantity": quantity,
                "minimum_quantity": minimum_quantity,
                "days_until_expiration": days_until_expiration,
                "risks": risks,
            }
        )

    return results
