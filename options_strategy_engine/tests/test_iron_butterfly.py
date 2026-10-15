from strategies.iron_butterfly import create_iron_butterfly


def test_iron_butterfly_structure():
    strategy = create_iron_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_buy_strike=23000,
        middle_strike=23200,
        call_buy_strike=23400,
        quantity=75,
        put_buy_premium=50,
        middle_put_premium=140,
        middle_call_premium=150,
        call_buy_premium=40,
    )

    assert strategy.name == "Iron Butterfly"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 4

    assert strategy.legs[0].strike == 23000
    assert strategy.legs[0].option_type == "PE"
    assert strategy.legs[0].position == "BUY"
    assert strategy.legs[0].quantity == 75

    assert strategy.legs[1].strike == 23200
    assert strategy.legs[1].option_type == "PE"
    assert strategy.legs[1].position == "SELL"
    assert strategy.legs[1].quantity == 75

    assert strategy.legs[2].strike == 23200
    assert strategy.legs[2].option_type == "CE"
    assert strategy.legs[2].position == "SELL"
    assert strategy.legs[2].quantity == 75

    assert strategy.legs[3].strike == 23400
    assert strategy.legs[3].option_type == "CE"
    assert strategy.legs[3].position == "BUY"
    assert strategy.legs[3].quantity == 75


def test_iron_butterfly_net_credit():
    strategy = create_iron_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_buy_strike=23000,
        middle_strike=23200,
        call_buy_strike=23400,
        quantity=75,
        put_buy_premium=50,
        middle_put_premium=140,
        middle_call_premium=150,
        call_buy_premium=40,
    )

    # Net premium per unit:
    # -50 + 140 + 150 - 40 = 200
    #
    # Net credit:
    # 200 × 75 = 15,000

    assert strategy.net_premium == 15000
    assert strategy.net_premium_received == 15000


def test_invalid_strike_order_rejected():
    try:
        create_iron_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=23200,
            middle_strike=23000,
            call_buy_strike=23400,
            quantity=75,
            put_buy_premium=50,
            middle_put_premium=140,
            middle_call_premium=150,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "strikes must satisfy "
            "put_buy < middle < call_buy"
        )


def test_equal_strikes_rejected():
    try:
        create_iron_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=23000,
            middle_strike=23000,
            call_buy_strike=23400,
            quantity=75,
            put_buy_premium=50,
            middle_put_premium=140,
            middle_call_premium=150,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "strikes must satisfy "
            "put_buy < middle < call_buy"
        )


def test_negative_premium_rejected():
    try:
        create_iron_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=23000,
            middle_strike=23200,
            call_buy_strike=23400,
            quantity=75,
            put_buy_premium=-10,
            middle_put_premium=140,
            middle_call_premium=150,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "option premiums cannot be negative"


def test_invalid_quantity_rejected():
    try:
        create_iron_butterfly(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=23000,
            middle_strike=23200,
            call_buy_strike=23400,
            quantity=0,
            put_buy_premium=50,
            middle_put_premium=140,
            middle_call_premium=150,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "quantity must be greater than 0"
