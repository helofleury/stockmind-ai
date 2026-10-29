
import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_FILE = DATA_DIR / "stockmind.db"
INVENTORY_FILE = DATA_DIR / "inventory.json"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database() -> None:
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                minimum_quantity INTEGER NOT NULL
                    CHECK (minimum_quantity >= 0),
                expiration_date TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL
                    CHECK (movement_type IN ('IN', 'OUT')),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                ),
                balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
                FOREIGN KEY (item_id) REFERENCES inventory(id)
                    ON DELETE RESTRICT
            )
            """
        )

        connection.commit()

        result = connection.execute(
            "SELECT COUNT(*) AS total FROM inventory"
        ).fetchone()

        if result["total"] == 0:
            if not INVENTORY_FILE.exists():
                raise FileNotFoundError(
                    f"Arquivo não encontrado: {INVENTORY_FILE}"
                )

            with INVENTORY_FILE.open(
                "r", encoding="utf-8"
            ) as file:
                items = json.load(file)

            connection.executemany(
                """
                INSERT INTO inventory (
                    id, name, quantity,
                    minimum_quantity, expiration_date
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["name"],
                        item["quantity"],
                        item["minimum_quantity"],
                        item["expiration_date"],
                    )
                    for item in items
                ],
            )

            connection.commit()

    finally:
        connection.close()


def get_inventory_records() -> list[dict]:
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, name, quantity,
                   minimum_quantity, expiration_date
            FROM inventory
            ORDER BY id
            """
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def create_inventory_record(item: dict) -> dict:
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO inventory (
                name, quantity, minimum_quantity, expiration_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                item["name"],
                item["quantity"],
                item["minimum_quantity"],
                item["expiration_date"],
            ),
        )

        connection.commit()

        row = connection.execute(
            "SELECT * FROM inventory WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

        return dict(row)

    finally:
        connection.close()


def update_inventory_record(
    item_id: int,
    updates: dict,
) -> dict | None:
    if not updates:
        return None

    allowed_fields = {
        "name", "quantity",
        "minimum_quantity", "expiration_date",
    }

    if not set(updates).issubset(allowed_fields):
        raise ValueError("Campo de atualização inválido.")

    connection = get_connection()

    try:
        fields = list(updates.keys())
        assignments = ", ".join(
            f"{field} = ?" for field in fields
        )
        values = [updates[field] for field in fields]
        values.append(item_id)

        cursor = connection.execute(
            f"UPDATE inventory SET {assignments} WHERE id = ?",
            values,
        )
        connection.commit()

        if cursor.rowcount == 0:
            return None

        row = connection.execute(
            "SELECT * FROM inventory WHERE id = ?",
            (item_id,),
        ).fetchone()

        return dict(row)

    finally:
        connection.close()


def delete_inventory_record(item_id: int) -> str:
    """Retorna 'deleted', 'not_found' ou 'has_movements'."""
    connection = get_connection()

    try:
        item = connection.execute(
            "SELECT id FROM inventory WHERE id = ?",
            (item_id,),
        ).fetchone()

        if item is None:
            return "not_found"

        movements = connection.execute(
            """
            SELECT id FROM stock_movements
            WHERE item_id = ?
            LIMIT 1
            """,
            (item_id,),
        ).fetchone()

        if movements is not None:
            return "has_movements"

        connection.execute(
            "DELETE FROM inventory WHERE id = ?",
            (item_id,),
        )
        connection.commit()

        return "deleted"

    finally:
        connection.close()


def create_stock_movement(
    item_id: int,
    movement_type: str,
    quantity: int,
    reason: str,
) -> dict | None:
    """Registra uma movimentação e atualiza o saldo atomicamente."""
    if movement_type not in {"IN", "OUT"}:
        raise ValueError("Tipo deve ser IN ou OUT.")

    if quantity <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        item = connection.execute(
            "SELECT quantity FROM inventory WHERE id = ?",
            (item_id,),
        ).fetchone()

        if item is None:
            connection.rollback()
            return None

        current_quantity = item["quantity"]

        if movement_type == "OUT" and quantity > current_quantity:
            connection.rollback()
            raise ValueError(
                "Estoque insuficiente para realizar essa saída."
            )

        if movement_type == "IN":
            new_balance = current_quantity + quantity
        else:
            new_balance = current_quantity - quantity

        connection.execute(
            "UPDATE inventory SET quantity = ? WHERE id = ?",
            (new_balance, item_id),
        )

        cursor = connection.execute(
            """
            INSERT INTO stock_movements (
                item_id, movement_type, quantity, reason, balance_after
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                item_id,
                movement_type,
                quantity,
                reason,
                new_balance,
            ),
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT
                m.id, m.item_id, i.name AS item_name,
                m.movement_type, m.quantity, m.reason,
                m.created_at, m.balance_after
            FROM stock_movements m
            JOIN inventory i ON i.id = m.item_id
            WHERE m.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        return dict(row)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_stock_movements(
    item_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    connection = get_connection()

    try:
        if item_id is None:
            rows = connection.execute(
                """
                SELECT
                    m.id, m.item_id, i.name AS item_name,
                    m.movement_type, m.quantity, m.reason,
                    m.created_at, m.balance_after
                FROM stock_movements m
                JOIN inventory i ON i.id = m.item_id
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT
                    m.id, m.item_id, i.name AS item_name,
                    m.movement_type, m.quantity, m.reason,
                    m.created_at, m.balance_after
                FROM stock_movements m
                JOIN inventory i ON i.id = m.item_id
                WHERE m.item_id = ?
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (item_id, limit),
            ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_inventory_summary() -> dict:
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_products,
                COALESCE(SUM(quantity), 0) AS total_units,
                SUM(
                    CASE WHEN quantity <= minimum_quantity
                    THEN 1 ELSE 0 END
                ) AS low_stock
            FROM inventory
            """
        ).fetchone()

        return {
            "total_products": row["total_products"],
            "total_units": row["total_units"],
            "low_stock": row["low_stock"] or 0,
        }

    finally:
        connection.close()
