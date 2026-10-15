from core.option_leg import OptionLeg
from strategies.bull_call_spread import create_bull_call_spread


def test_bull_call_spread_structure():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    assert strategy.name == "Bull Call Spread"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    buy_leg = strategy.legs[0]
    sell_leg = strategy.legs[1]

    assert isinstance(buy_leg, OptionLeg)
    assert isinstance(sell_leg, OptionLeg)

    assert buy_leg.strike == 23200
    assert buy_leg.option_type == "CE"
    assert buy_leg.position == "BUY"

    assert sell_leg.strike == 23400
    assert sell_leg.option_type == "CE"
    assert sell_leg.position == "SELL"


def test_bull_call_spread_net_debit():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    # Buy 23200 CE = -11,250
    # Sell 23400 CE = +6,000
    # Net debit = 5,250
    assert strategy.net_premium == -5250
    assert strategy.net_premium_paid == 5250
    assert strategy.net_premium_received == 0


def test_invalid_strike_order():
    try:
        create_bull_call_spread(
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
        create_bull_call_spread(
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
