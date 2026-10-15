"""Small tests for the NIFTY 50 descriptive analysis project."""

import numpy as np
import pytest

from nifty_analysis import analyze, download_data, load_data


@pytest.fixture(scope="module")
def data():
    """Download once, save CSV, load it back, and share across tests."""
    download_data()
    return load_data()


def test_columns_exist(data):
    expected = {"Open", "High", "Low", "Close", "Volume"}
    assert expected.issubset(set(data.columns))


def test_data_not_empty(data):
    assert len(data) > 0


def test_values_are_finite(data):
    stats = analyze(data)
    for key, value in stats.items():
        if isinstance(value, (int, float)):
            assert np.isfinite(value), f"{key} is not finite: {value}"


def test_pos_neg_days_within_trading_days(data):
    stats = analyze(data)
    assert stats["positive_days"] + stats["negative_days"] <= stats["trading_days"]
