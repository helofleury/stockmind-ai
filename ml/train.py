
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "ml" / "data" / "historical_consumption.csv"
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
MODEL_FILE = MODEL_DIR / "demand_forecasting.joblib"
METRICS_FILE = MODEL_DIR / "evaluation_metrics.csv"

FEATURES = [
    "product_id",
    "day_of_week",
    "month",
    "is_weekend",
    "lag_1",
    "lag_7",
    "rolling_mean_7",
]

TARGET = "consumption"


def prepare_data() -> pd.DataFrame:
    """Carrega os dados e cria atributos com informações passadas."""

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset não encontrado: {DATA_FILE}. "
            "Execute primeiro ml/data/generate_dataset.py."
        )

    df = pd.read_csv(DATA_FILE, parse_dates=["date"])
    df = df.sort_values(["product_id", "date"]).copy()

    grouped = df.groupby("product_id", group_keys=False)

    df["lag_1"] = grouped["consumption"].shift(1)
    df["lag_7"] = grouped["consumption"].shift(7)

    df["rolling_mean_7"] = grouped["consumption"].transform(
        lambda series: series.shift(1).rolling(window=7).mean()
    )

    df = df.dropna(subset=FEATURES + [TARGET]).copy()

    return df


def main() -> None:
    df = prepare_data()

    # Divisão temporal: cada produto usa as datas mais antigas
    # para treinamento e as datas mais recentes para teste.
    train_parts = []
    test_parts = []

    for _, product_df in df.groupby("product_id"):
        product_df = product_df.sort_values("date")
        split_index = int(len(product_df) * 0.8)

        train_parts.append(product_df.iloc[:split_index])
        test_parts.append(product_df.iloc[split_index:])

    train_df = pd.concat(train_parts).sort_values("date")
    test_df = pd.concat(test_parts).sort_values("date")

    X_train = train_df[FEATURES]
    y_train = train_df[TARGET]

    X_test = test_df[FEATURES]
    y_test = test_df[TARGET]

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    # Baseline: prevê o mesmo consumo observado no dia anterior.
    baseline_predictions = test_df["lag_1"].to_numpy()

    model_mae = mean_absolute_error(y_test, predictions)
    model_rmse = np.sqrt(mean_squared_error(y_test, predictions))

    baseline_mae = mean_absolute_error(y_test, baseline_predictions)
    baseline_rmse = np.sqrt(
        mean_squared_error(y_test, baseline_predictions)
    )

    metrics = pd.DataFrame(
        [
            {
                "model": "Random Forest",
                "mae": model_mae,
                "rmse": model_rmse,
            },
            {
                "model": "Baseline - dia anterior",
                "mae": baseline_mae,
                "rmse": baseline_rmse,
            },
        ]
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "target": TARGET,
            "product_names": (
                df[["product_id", "product_name"]]
                .drop_duplicates()
                .set_index("product_id")["product_name"]
                .to_dict()
            ),
            "last_date": df["date"].max().strftime("%Y-%m-%d"),
        },
        MODEL_FILE,
    )

    metrics.to_csv(METRICS_FILE, index=False)

    print("\n=== StockMind AI | Avaliação do modelo ===")
    print(f"Registros para treinamento: {len(train_df)}")
    print(f"Registros para teste: {len(test_df)}")
    print(f"Período de teste: {test_df['date'].min().date()} até "
          f"{test_df['date'].max().date()}")

    print("\nMétricas:")
    print(metrics.round(3).to_string(index=False))

    print(f"\nModelo salvo em: {MODEL_FILE}")
    print(f"Métricas salvas em: {METRICS_FILE}")


if __name__ == "__main__":
    main()
