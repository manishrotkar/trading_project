from strategies.short_put_butterfly import create_short_put_butterfly


def test_short_put_butterfly_structure():
    strategy = create_short_put_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_put_premium=80,
        middle_put_premium=150,
        higher_put_premium=250,
    )

    assert strategy.name == "Short Put Butterfly"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 3

    assert strategy.legs[0].strike == 23000
    assert strategy.legs[0].option_type == "PE"
    assert strategy.legs[0].position == "SELL"
    assert strategy.legs[0].quantity == 75

    assert strategy.legs[1].strike == 23200
    assert strategy.legs[1].option_type == "PE"
    assert strategy.legs[1].position == "BUY"
    assert strategy.legs[1].quantity == 150

    assert strategy.legs[2].strike == 23400
    assert strategy.legs[2].option_type == "PE"
    assert strategy.legs[2].position == "SELL"
    assert strategy.legs[2].quantity == 75


def test_short_put_butterfly_net_credit():
    strategy = create_short_put_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_put_premium=80,
        middle_put_premium=150,
        higher_put_premium=250,
    )

    # Net premium per unit:
    # 80 - (150 × 2) + 250 = 30
    #
    # Net credit:
    # 30 × 75 = 2,250

    assert strategy.net_premium == 2250
    assert strategy.net_premium_received == 2250


def test_unequal_strikes_rejected():
    try:
        create_short_put_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            middle_strike=23200,
            higher_strike=23500,
            quantity=75,
            lower_put_premium=80,
            middle_put_premium=150,
            higher_put_premium=250,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "strikes must be equally spaced"


def test_invalid_strike_order_rejected():
    try:
        create_short_put_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23400,
            middle_strike=23200,
            higher_strike=23000,
            quantity=75,
            lower_put_premium=80,
            middle_put_premium=150,
            higher_put_premium=250,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "strikes must satisfy lower < middle < higher"


def test_negative_premium_rejected():
    try:
        create_short_put_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            middle_strike=23200,
            higher_strike=23400,
            quantity=75,
            lower_put_premium=-10,
            middle_put_premium=150,
            higher_put_premium=250,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "option premiums cannot be negative"


def test_invalid_quantity_rejected():
    try:
        create_short_put_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            lower_strike=23000,
            middle_strike=23200,
            higher_strike=23400,
            quantity=0,
            lower_put_premium=80,
            middle_put_premium=150,
            higher_put_premium=250,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "quantity must be greater than 0"
