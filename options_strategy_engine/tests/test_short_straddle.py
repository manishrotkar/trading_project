from core.option_leg import OptionLeg
from strategies.short_straddle import create_short_straddle


def test_short_straddle_structure():
    strategy = create_short_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    assert strategy.name == "Short Straddle"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    call_leg = strategy.legs[0]
    put_leg = strategy.legs[1]

    assert isinstance(call_leg, OptionLeg)
    assert isinstance(put_leg, OptionLeg)

    assert call_leg.strike == 23200
    assert call_leg.option_type == "CE"
    assert call_leg.position == "SELL"

    assert put_leg.strike == 23200
    assert put_leg.option_type == "PE"
    assert put_leg.position == "SELL"


def test_short_straddle_net_credit():
    strategy = create_short_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # Total premium received = 290 × 75 = 21,750

    assert strategy.net_premium == 21750
    assert strategy.net_premium_received == 21750
    assert strategy.net_premium_paid == 0


def test_negative_premium_rejected():
    try:
        create_short_straddle(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=23200,
            quantity=75,
            call_premium=-10,
            put_premium=140,
        )
        assert False
    except ValueError:
        assert True


def test_invalid_strike_rejected():
    try:
        create_short_straddle(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=0,
            quantity=75,
            call_premium=150,
            put_premium=140,
        )
        assert False
    except ValueError:
        assert True
