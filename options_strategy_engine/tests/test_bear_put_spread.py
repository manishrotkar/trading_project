from core.option_leg import OptionLeg
from strategies.bear_put_spread import create_bear_put_spread


def test_bear_put_spread_structure():
    strategy = create_bear_put_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_put_premium=80,
        higher_put_premium=150,
    )

    assert strategy.name == "Bear Put Spread"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    buy_leg = strategy.legs[0]
    sell_leg = strategy.legs[1]

    assert isinstance(buy_leg, OptionLeg)
    assert isinstance(sell_leg, OptionLeg)

    assert buy_leg.strike == 23400
    assert buy_leg.option_type == "PE"
    assert buy_leg.position == "BUY"

    assert sell_leg.strike == 23200
    assert sell_leg.option_type == "PE"
    assert sell_leg.position == "SELL"


def test_bear_put_spread_net_debit():
    strategy = create_bear_put_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_put_premium=80,
        higher_put_premium=150,
    )

    # Buy 23400 PE = -11,250
    # Sell 23200 PE = +6,000
    # Net debit       = -5,250

    assert strategy.net_premium == -5250
    assert strategy.net_premium_paid == 5250
    assert strategy.net_premium_received == 0


def test_invalid_strike_order():
    try:
        create_bear_put_spread(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23400,
            higher_strike=23200,
            quantity=75,
            lower_put_premium=80,
            higher_put_premium=150,
        )
        assert False
    except ValueError:
        assert True


def test_equal_strikes_rejected():
    try:
        create_bear_put_spread(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23200,
            higher_strike=23200,
            quantity=75,
            lower_put_premium=80,
            higher_put_premium=150,
        )
        assert False
    except ValueError:
        assert True
