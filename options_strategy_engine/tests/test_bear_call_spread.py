from core.option_leg import OptionLeg
from strategies.bear_call_spread import create_bear_call_spread


def test_bear_call_spread_structure():
    strategy = create_bear_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    assert strategy.name == "Bear Call Spread"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    sell_leg = strategy.legs[0]
    buy_leg = strategy.legs[1]

    assert isinstance(sell_leg, OptionLeg)
    assert isinstance(buy_leg, OptionLeg)

    assert sell_leg.strike == 23200
    assert sell_leg.option_type == "CE"
    assert sell_leg.position == "SELL"

    assert buy_leg.strike == 23400
    assert buy_leg.option_type == "CE"
    assert buy_leg.position == "BUY"


def test_bear_call_spread_net_credit():
    strategy = create_bear_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    # Sell 23200 CE = +11,250
    # Buy 23400 CE  = -6,000
    # Net credit      = +5,250

    assert strategy.net_premium == 5250
    assert strategy.net_premium_received == 5250
    assert strategy.net_premium_paid == 0


def test_invalid_strike_order():
    try:
        create_bear_call_spread(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23400,
            higher_strike=23200,
            quantity=75,
            lower_call_premium=100,
            higher_call_premium=50,
        )
        assert False
    except ValueError:
        assert True


def test_equal_strikes_rejected():
    try:
        create_bear_call_spread(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23200,
            higher_strike=23200,
            quantity=75,
            lower_call_premium=100,
            higher_call_premium=50,
        )
        assert False
    except ValueError:
        assert True
