import pytest

from core.option_leg import OptionLeg
from strategies.call_butterfly import create_long_call_butterfly


def test_long_call_butterfly_structure():
    strategy = create_long_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    assert strategy.name == "Long Call Butterfly"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 3

    lower_leg = strategy.legs[0]
    middle_leg = strategy.legs[1]
    higher_leg = strategy.legs[2]

    assert isinstance(lower_leg, OptionLeg)
    assert isinstance(middle_leg, OptionLeg)
    assert isinstance(higher_leg, OptionLeg)

    assert lower_leg.strike == 23000
    assert lower_leg.option_type == "CE"
    assert lower_leg.position == "BUY"
    assert lower_leg.quantity == 75

    assert middle_leg.strike == 23200
    assert middle_leg.option_type == "CE"
    assert middle_leg.position == "SELL"
    assert middle_leg.quantity == 150

    assert higher_leg.strike == 23400
    assert higher_leg.option_type == "CE"
    assert higher_leg.position == "BUY"
    assert higher_leg.quantity == 75


def test_long_call_butterfly_net_debit():
    strategy = create_long_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    # Net premium per unit:
    # 300 - (2 × 200) + 120 = 20 debit
    #
    # Total debit = 20 × 75 = 1,500

    assert strategy.net_premium == -1500
    assert strategy.net_premium_paid == 1500
    assert strategy.net_premium_received == 0


def test_unequal_strikes_rejected():
    with pytest.raises(ValueError):
        create_long_call_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            middle_strike=23200,
            higher_strike=23500,
            quantity=75,
            lower_call_premium=300,
            middle_call_premium=200,
            higher_call_premium=120,
        )


def test_invalid_strike_order_rejected():
    with pytest.raises(ValueError):
        create_long_call_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23400,
            middle_strike=23200,
            higher_strike=23000,
            quantity=75,
            lower_call_premium=300,
            middle_call_premium=200,
            higher_call_premium=120,
        )


def test_negative_premium_rejected():
    with pytest.raises(ValueError):
        create_long_call_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            middle_strike=23200,
            higher_strike=23400,
            quantity=75,
            lower_call_premium=-10,
            middle_call_premium=200,
            higher_call_premium=120,
        )


def test_invalid_quantity_rejected():
    with pytest.raises(ValueError):
        create_long_call_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            middle_strike=23200,
            higher_strike=23400,
            quantity=0,
            lower_call_premium=300,
            middle_call_premium=200,
            higher_call_premium=120,
        )
