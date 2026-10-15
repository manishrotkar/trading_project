import pytest

from core.option_leg import OptionLeg
from strategies.short_strangle import create_short_strangle


def test_short_strangle_structure():
    strategy = create_short_strangle(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_strike=23000,
        call_strike=23400,
        quantity=75,
        put_premium=100,
        call_premium=120,
    )

    assert strategy.name == "Short Strangle"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    put_leg = strategy.legs[0]
    call_leg = strategy.legs[1]

    assert isinstance(put_leg, OptionLeg)
    assert isinstance(call_leg, OptionLeg)

    assert put_leg.strike == 23000
    assert put_leg.option_type == "PE"
    assert put_leg.position == "SELL"

    assert call_leg.strike == 23400
    assert call_leg.option_type == "CE"
    assert call_leg.position == "SELL"

    assert put_leg.quantity == 75
    assert call_leg.quantity == 75


def test_short_strangle_net_credit():
    strategy = create_short_strangle(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_strike=23000,
        call_strike=23400,
        quantity=75,
        put_premium=100,
        call_premium=120,
    )

    # Total premium = 100 + 120 = 220
    # Net credit = 220 × 75 = 16,500

    assert strategy.net_premium == 16500
    assert strategy.net_premium_received == 16500
    assert strategy.net_premium_paid == 0


def test_invalid_strike_order():
    with pytest.raises(ValueError):
        create_short_strangle(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_strike=23400,
            call_strike=23000,
            quantity=75,
            put_premium=100,
            call_premium=120,
        )


def test_equal_strikes_rejected():
    with pytest.raises(ValueError):
        create_short_strangle(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_strike=23200,
            call_strike=23200,
            quantity=75,
            put_premium=100,
            call_premium=120,
        )


def test_negative_premium_rejected():
    with pytest.raises(ValueError):
        create_short_strangle(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_strike=23000,
            call_strike=23400,
            quantity=75,
            put_premium=-10,
            call_premium=120,
        )


def test_invalid_quantity_rejected():
    with pytest.raises(ValueError):
        create_short_strangle(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_strike=23000,
            call_strike=23400,
            quantity=0,
            put_premium=100,
            call_premium=120,
        )
