import pandas as pd
import pytest

from ml.predict import forecast_demand


def test_forecast_returns_seven_days():
    forecast = forecast_demand(product_id=1, horizon=7)

    assert len(forecast) == 7
    assert list(forecast.columns) == [
        "date",
        "product_id",
        "product_name",
        "predicted_consumption",
    ]


def test_forecast_has_consecutive_dates():
    forecast = forecast_demand(product_id=1, horizon=7)

    dates = pd.to_datetime(forecast["date"])
    differences = dates.diff().dropna()

    assert (differences == pd.Timedelta(days=1)).all()


def test_forecast_values_are_non_negative():
    forecast = forecast_demand(product_id=1, horizon=7)

    assert (forecast["predicted_consumption"] >= 0).all()


def test_forecast_rejects_invalid_horizon():
    with pytest.raises(ValueError):
        forecast_demand(product_id=1, horizon=0)

    with pytest.raises(ValueError):
        forecast_demand(product_id=1, horizon=31)


def test_forecast_rejects_unknown_product():
    with pytest.raises(ValueError, match="não encontrado"):
        forecast_demand(product_id=999, horizon=7)
