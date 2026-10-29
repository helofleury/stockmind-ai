
from pathlib import Path

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "ml" / "data" / "historical_consumption.csv"
MODEL_FILE = PROJECT_ROOT / "ml" / "models" / "demand_forecasting.joblib"


def forecast_demand(
    product_id: int,
    horizon: int = 7,
) -> pd.DataFrame:
    """Prevê o consumo futuro de um produto usando o modelo treinado."""

    if horizon < 1 or horizon > 30:
        raise ValueError("O horizonte deve estar entre 1 e 30 dias.")

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            "Modelo não encontrado. Execute primeiro: python ml/train.py"
        )

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            "Dataset não encontrado. Execute primeiro o gerador de dados."
        )

    artifact = joblib.load(MODEL_FILE)
    model = artifact["model"]
    features = artifact["features"]
    product_names = artifact["product_names"]

    if product_id not in product_names:
        raise ValueError(f"Produto com ID {product_id} não encontrado.")

    history = pd.read_csv(DATA_FILE, parse_dates=["date"])
    history = history[history["product_id"] == product_id].sort_values("date")

    if history.empty:
        raise ValueError(f"Não existe histórico para o produto {product_id}.")

    consumption_history = history["consumption"].astype(float).tolist()
    last_date = history["date"].max()

    predictions = []

    for step in range(1, horizon + 1):
        forecast_date = last_date + pd.Timedelta(days=step)

        previous_seven = consumption_history[-7:]
        previous_day = consumption_history[-1]

        row = pd.DataFrame(
            [
                {
                    "product_id": product_id,
                    "day_of_week": forecast_date.day_of_week,
                    "month": forecast_date.month,
                    "is_weekend": int(forecast_date.day_of_week >= 5),
                    "lag_1": previous_day,
                    "lag_7": consumption_history[-7],
                    "rolling_mean_7": sum(previous_seven) / len(previous_seven),
                }
            ]
        )

        prediction = max(0.0, float(model.predict(row[features])[0]))
        rounded_prediction = round(prediction, 2)

        predictions.append(
            {
                "date": forecast_date.strftime("%Y-%m-%d"),
                "product_id": product_id,
                "product_name": product_names[product_id],
                "predicted_consumption": rounded_prediction,
            }
        )

        # Usa a previsão como entrada para o próximo dia.
        consumption_history.append(prediction)

    return pd.DataFrame(predictions)


if __name__ == "__main__":
    for product_id in [1, 2, 3, 4, 5]:
        forecast = forecast_demand(product_id=product_id, horizon=7)

        print(f"\n=== {forecast.iloc[0]['product_name']} ===")
        print(forecast.to_string(index=False))
        print(
            "Consumo previsto para 7 dias:",
            round(forecast["predicted_consumption"].sum(), 2),
            "unidades",
        )
