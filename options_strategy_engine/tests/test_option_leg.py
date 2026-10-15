from core.option_leg import OptionLeg


def test_buy_call():
    leg = OptionLeg(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        option_type="CE",
        position="BUY",
        quantity=75,
        entry_premium=150,
    )

    assert leg.index_name == "NIFTY"
    assert leg.strike == 23200
    assert leg.option_type == "CE"
    assert leg.position == "BUY"
    assert leg.quantity == 75
    assert leg.entry_premium == 150

    assert leg.premium_value == 11250
    assert leg.signed_premium == -11250


def test_sell_call():
    leg = OptionLeg(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23400,
        option_type="CE",
        position="SELL",
        quantity=75,
        entry_premium=80,
    )

    assert leg.premium_value == 6000
    assert leg.signed_premium == 6000


def test_invalid_option_type():
    try:
        OptionLeg(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=23200,
            option_type="XX",
            position="BUY",
            quantity=75,
            entry_premium=100,
        )
        assert False
    except ValueError:
        assert True


def test_invalid_strike():
    try:
        OptionLeg(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=0,
            option_type="CE",
            position="BUY",
            quantity=75,
            entry_premium=100,
        )
        assert False
    except ValueError:
        assert True
