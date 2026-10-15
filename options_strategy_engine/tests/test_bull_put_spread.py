from core.option_leg import OptionLeg
from strategies.bull_put_spread import create_bull_put_spread


def test_bull_put_spread_structure():
    strategy = create_bull_put_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        higher_strike=23200,
        quantity=75,
        lower_put_premium=70,
        higher_put_premium=120,
    )

    assert strategy.name == "Bull Put Spread"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    sell_leg = strategy.legs[0]
    buy_leg = strategy.legs[1]

    assert isinstance(sell_leg, OptionLeg)
    assert isinstance(buy_leg, OptionLeg)

    assert sell_leg.strike == 23200
    assert sell_leg.option_type == "PE"
    assert sell_leg.position == "SELL"

    assert buy_leg.strike == 23000
    assert buy_leg.option_type == "PE"
    assert buy_leg.position == "BUY"


def test_bull_put_spread_net_credit():
    strategy = create_bull_put_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        higher_strike=23200,
        quantity=75,
        lower_put_premium=70,
        higher_put_premium=120,
    )

    # Sell 23200 PE = +9,000
    # Buy 23000 PE  = -5,250
    # Net credit     = +3,750

    assert strategy.net_premium == 3750
    assert strategy.net_premium_received == 3750
    assert strategy.net_premium_paid == 0


def test_invalid_strike_order():
    try:
        create_bull_put_spread(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23200,
            higher_strike=23000,
            quantity=75,
            lower_put_premium=70,
            higher_put_premium=120,
        )
        assert False
    except ValueError:
        assert True


def test_equal_strikes_rejected():
    try:
        create_bull_put_spread(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            higher_strike=23000,
            quantity=75,
            lower_put_premium=70,
            higher_put_premium=120,
        )
        assert False
    except ValueError:
        assert True
