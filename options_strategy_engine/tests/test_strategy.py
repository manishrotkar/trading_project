from core.option_leg import OptionLeg
from core.strategy import Strategy


def test_add_leg():
    strategy = Strategy(
        name="Test Strategy",
        underlying="NIFTY",
    )

    leg = OptionLeg(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        option_type="CE",
        position="BUY",
        quantity=75,
        entry_premium=150,
    )

    strategy.add_leg(leg)

    assert strategy.leg_count == 1
    assert strategy.legs[0] == leg


def test_net_premium_paid():
    strategy = Strategy(
        name="Test Strategy",
        underlying="NIFTY",
    )

    strategy.add_leg(
        OptionLeg(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=23200,
            option_type="CE",
            position="BUY",
            quantity=75,
            entry_premium=150,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=23400,
            option_type="CE",
            position="SELL",
            quantity=75,
            entry_premium=80,
        )
    )

    assert strategy.leg_count == 2

    # Buy: -11,250
    # Sell: +6,000
    # Net: -5,250
    assert strategy.net_premium == -5250
    assert strategy.net_premium_paid == 5250
    assert strategy.net_premium_received == 0


def test_net_premium_received():
    strategy = Strategy(
        name="Credit Strategy",
        underlying="NIFTY",
    )

    strategy.add_leg(
        OptionLeg(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=23200,
            option_type="PE",
            position="SELL",
            quantity=75,
            entry_premium=120,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name="NIFTY",
            expiry="2026-10-01",
            strike=23000,
            option_type="PE",
            position="BUY",
            quantity=75,
            entry_premium=70,
        )
    )

    # Sell: +9,000
    # Buy:  -5,250
    # Net:  +3,750
    assert strategy.net_premium == 3750
    assert strategy.net_premium_paid == 0
    assert strategy.net_premium_received == 3750


def test_wrong_underlying_rejected():
    strategy = Strategy(
        name="NIFTY Strategy",
        underlying="NIFTY",
    )

    banknifty_leg = OptionLeg(
        index_name="BANKNIFTY",
        expiry="2026-10-01",
        strike=55000,
        option_type="CE",
        position="BUY",
        quantity=35,
        entry_premium=200,
    )

    try:
        strategy.add_leg(banknifty_leg)
        assert False
    except ValueError:
        assert True


def test_empty_strategy_validation():
    strategy = Strategy(
        name="Empty Strategy",
        underlying="NIFTY",
    )

    try:
        strategy.validate()
        assert False
    except ValueError:
        assert True
