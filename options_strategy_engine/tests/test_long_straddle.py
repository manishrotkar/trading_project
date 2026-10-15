from core.option_leg import OptionLeg
from strategies.long_straddle import create_long_straddle


def test_long_straddle_structure():
    strategy = create_long_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    assert strategy.name == "Long Straddle"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 2

    call_leg = strategy.legs[0]
    put_leg = strategy.legs[1]

    assert isinstance(call_leg, OptionLeg)
    assert isinstance(put_leg, OptionLeg)

    assert call_leg.strike == 23200
    assert call_leg.option_type == "CE"
    assert call_leg.position == "BUY"

    assert put_leg.strike == 23200
    assert put_leg.option_type == "PE"
    assert put_leg.position == "BUY"


def test_long_straddle_net_debit():
    strategy = create_long_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # Total premium = 150 + 140 = 290
    # Net debit = 290 × 75 = 21,750

    assert strategy.net_premium == -21750
    assert strategy.net_premium_paid == 21750
    assert strategy.net_premium_received == 0


def test_negative_premium_rejected():
    try:
        create_long_straddle(
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
        create_long_straddle(
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
