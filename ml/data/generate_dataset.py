
from pathlib import Path

import numpy as np
import pandas as pd


# Caminhos do projeto
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "data"
OUTPUT_FILE = OUTPUT_DIR / "historical_consumption.csv"

# Configuração para reproduzir os mesmos dados em cada execução
RANDOM_SEED = 42
START_DATE = "2025-01-01"
END_DATE = "2026-10-28"

# Dados demonstrativos: parâmetros simulados, não dados reais hospitalares.
PRODUCTS = [
    {
        "product_id": 1,
        "product_name": "Luvas descartáveis",
        "base_daily_consumption": 28,
        "weekly_variation": 0.12,
        "trend_per_day": 0.005,
    },
    {
        "product_id": 2,
        "product_name": "Seringas descartáveis",
        "base_daily_consumption": 35,
        "weekly_variation": 0.08,
        "trend_per_day": 0.002,
    },
    {
        "product_id": 3,
        "product_name": "Máscaras cirúrgicas",
        "base_daily_consumption": 22,
        "weekly_variation": 0.15,
        "trend_per_day": 0.003,
    },
    {
        "product_id": 4,
        "product_name": "Gazes esterilizadas",
        "base_daily_consumption": 18,
        "weekly_variation": 0.10,
        "trend_per_day": 0.001,
    },
    {
        "product_id": 5,
        "product_name": "Álcool 70%",
        "base_daily_consumption": 15,
        "weekly_variation": 0.07,
        "trend_per_day": 0.002,
    },
]


def generate_dataset() -> pd.DataFrame:
    """Gera consumo diário sintético para cada produto."""

    rng = np.random.default_rng(RANDOM_SEED)

    dates = pd.date_range(
        start=START_DATE,
        end=END_DATE,
        freq="D",
    )

    records = []

    for product in PRODUCTS:
        base = product["base_daily_consumption"]
        weekly_variation = product["weekly_variation"]
        trend_per_day = product["trend_per_day"]

        for day_index, date in enumerate(dates):
            # Simula menor ou maior consumo conforme o dia da semana.
            # Segunda-feira = 0; domingo = 6.
            if date.dayofweek < 5:
                weekday_factor = 1 + weekly_variation
            else:
                weekday_factor = 1 - weekly_variation

            # Simula variação gradual de consumo ao longo do ano.
            trend_factor = 1 + trend_per_day * day_index

            # Simula oscilações aleatórias no consumo.
            random_factor = rng.normal(loc=1.0, scale=0.12)

            # Simula períodos com demanda sazonal.
            seasonal_factor = 1 + 0.10 * np.sin(
                2 * np.pi * date.dayofyear / 365
            )

            consumption = (
                base
                * weekday_factor
                * trend_factor
                * random_factor
                * seasonal_factor
            )

            consumption = max(0, int(round(consumption)))

            records.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "consumption": consumption,
                    "day_of_week": date.dayofweek,
                    "month": date.month,
                    "is_weekend": int(date.dayofweek >= 5),
                }
            )

    dataset = pd.DataFrame(records)

    return dataset


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset()
    dataset.to_csv(OUTPUT_FILE, index=False)

    print("Dataset sintético gerado com sucesso!")
    print(f"Arquivo: {OUTPUT_FILE}")
    print(f"Total de registros: {len(dataset):,}")
    print(f"Produtos: {dataset['product_id'].nunique()}")
    print(
        f"Período: {dataset['date'].min()} até "
        f"{dataset['date'].max()}"
    )
    print("\nPrimeiras linhas:")
    print(dataset.head(10).to_string(index=False))
    print("\nConsumo médio por produto:")
    print(
        dataset.groupby("product_name")["consumption"]
        .mean()
        .round(2)
        .to_string()
    )


if __name__ == "__main__":
    main()
