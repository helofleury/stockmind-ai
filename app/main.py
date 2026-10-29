
import sqlite3
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import (
    create_inventory_record,
    create_stock_movement,
    delete_inventory_record,
    get_inventory_records,
    get_inventory_summary,
    get_stock_movements,
    initialize_database,
    update_inventory_record,
)
from app.inventory import analyze_inventory
from app.agent import (
    generate_inventory_report,
    generate_inventory_chat_response,
)
from ml.predict import forecast_demand


app = FastAPI(
    title="StockMind AI",
    description="API demonstrativa para análise de estoque hospitalar fictício.",
    version="1.3.0",
)


class InventoryItem(BaseModel):
    id: int
    name: str
    quantity: int = Field(ge=0)
    minimum_quantity: int = Field(ge=0)
    expiration_date: date


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    quantity: int = Field(ge=0)
    minimum_quantity: int = Field(ge=0)
    expiration_date: date


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    quantity: int | None = Field(default=None, ge=0)
    minimum_quantity: int | None = Field(default=None, ge=0)
    expiration_date: date | None = None


class StockMovementCreate(BaseModel):
    movement_type: str = Field(pattern="^(IN|OUT)$")
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=250)


class ChatHistoryMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class InventoryChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=10,
    )


def load_inventory() -> list[InventoryItem]:
    try:
        initialize_database()
        return [
            InventoryItem.model_validate(item)
            for item in get_inventory_records()
        ]
    except (sqlite3.Error, OSError, ValueError) as error:
        print(f"Erro no banco: {error}", flush=True)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível carregar o estoque.",
        ) from error


@app.get("/")
def home():
    return {
        "project": "StockMind AI",
        "message": "API funcionando!",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/inventory")
def get_inventory():
    return load_inventory()


@app.get("/inventory/analyze")
def get_inventory_analysis():
    items = load_inventory()
    results = analyze_inventory([
        item.model_dump(mode="json") for item in items
    ])

    return {
        "total_items": len(results),
        "items_with_risks": sum(bool(item["risks"]) for item in results),
        "results": results,
    }


@app.get("/inventory/ai-analysis")
def get_inventory_ai_analysis():
    items = load_inventory()
    results = analyze_inventory([
        item.model_dump(mode="json") for item in items
    ])

    try:
        report = generate_inventory_report(results)
        return {
            "project": "StockMind AI",
            "report": report,
            "analyzed_items": len(results),
        }
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        print(f"Erro Gemini: {type(error).__name__}: {error}", flush=True)
        raise HTTPException(
            status_code=502,
            detail="Falha ao gerar o relatório. Consulte o terminal da API.",
        ) from error


@app.post("/inventory/chat")
def inventory_chat(request: InventoryChatRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Digite uma pergunta antes de enviar.",
        )

    # Carrega os dados atuais do banco a cada pergunta.
    items = load_inventory()
    results = analyze_inventory([
        item.model_dump(mode="json") for item in items
    ])

    history = [
        message.model_dump()
        for message in request.history
    ]

    try:
        answer = generate_inventory_chat_response(
            question=question,
            inventory_results=results,
            conversation_history=history,
        )

        return {
            "project": "StockMind AI",
            "question": question,
            "answer": answer,
            "analyzed_items": len(results),
        }

    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except Exception as error:
        print(f"Erro no chat Gemini: {type(error).__name__}: {error}", flush=True)
        raise HTTPException(
            status_code=502,
            detail="Falha ao responder. Consulte o terminal da API.",
        ) from error


@app.post("/inventory", status_code=201)
def create_inventory(item: InventoryItemCreate):
    initialize_database()

    try:
        created = create_inventory_record(item.model_dump(mode="json"))
        return {"message": "Produto cadastrado.", "item": created}
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="Não foi possível cadastrar esse produto.",
        ) from error
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail="Erro ao cadastrar produto.",
        ) from error


@app.patch("/inventory/{item_id}")
def update_inventory(item_id: int, item: InventoryItemUpdate):
    initialize_database()
    updates = item.model_dump(mode="json", exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Envie pelo menos um campo para atualizar.",
        )

    if any(value is None for value in updates.values()):
        raise HTTPException(
            status_code=422,
            detail="Os campos enviados não podem ser nulos.",
        )

    try:
        updated = update_inventory_record(item_id, updates)
        if updated is None:
            raise HTTPException(
                status_code=404,
                detail="Produto não encontrado.",
            )
        return {"message": "Produto atualizado.", "item": updated}
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar produto.",
        ) from error


@app.delete("/inventory/{item_id}")
def delete_inventory(item_id: int):
    initialize_database()

    try:
        result = delete_inventory_record(item_id)
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir produto.",
        ) from error

    if result == "not_found":
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado.",
        )

    if result == "has_movements":
        raise HTTPException(
            status_code=409,
            detail=(
                "Este produto possui movimentações registradas "
                "e não pode ser excluído para preservar o histórico."
            ),
        )

    return {"message": "Produto excluído com sucesso.", "id": item_id}


@app.post("/inventory/{item_id}/movements", status_code=201)
def register_stock_movement(
    item_id: int,
    movement: StockMovementCreate,
):
    initialize_database()

    try:
        result = create_stock_movement(
            item_id=item_id,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            reason=movement.reason.strip(),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail="Erro ao registrar movimentação.",
        ) from error

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado.",
        )

    return {"message": "Movimentação registrada.", "movement": result}


@app.get("/inventory/{item_id}/movements")
def get_item_movements(
    item_id: int,
    limit: int = Query(default=100, ge=1, le=500),
):
    initialize_database()
    items = get_inventory_records()

    if not any(item["id"] == item_id for item in items):
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado.",
        )

    return get_stock_movements(item_id=item_id, limit=limit)


@app.get("/movements")
def get_recent_movements(
    limit: int = Query(default=100, ge=1, le=500),
):
    initialize_database()
    return get_stock_movements(limit=limit)


@app.get("/inventory/summary")
def inventory_summary():
    initialize_database()
    summary = get_inventory_summary()
    items = load_inventory()
    today = date.today()

    expired = sum(
        item.expiration_date < today for item in items
    )
    expiring_soon = sum(
        0 <= (item.expiration_date - today).days <= 30
        for item in items
    )

    return {
        **summary,
        "expired_products": expired,
        "expiring_within_30_days": expiring_soon,
    }
    
@app.get("/ml/forecast/{product_id}")
def get_demand_forecast(
    product_id: int,
    horizon: int = 7,
):
    """Retorna a previsão de consumo de um produto."""

    try:
        forecast = forecast_demand(
            product_id=product_id,
            horizon=horizon,
        )

        records = forecast.to_dict(orient="records")

        for record in records:
            record["date"] = str(record["date"])
            record["predicted_consumption"] = round(
                float(record["predicted_consumption"]), 2
            )

        return {
            "project": "StockMind AI",
            "product_id": product_id,
            "horizon_days": horizon,
            "forecast": records,
            "total_predicted_consumption": round(
                sum(
                    item["predicted_consumption"]
                    for item in records
                ),
                2,
            ),
        }

    except ValueError as error:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
