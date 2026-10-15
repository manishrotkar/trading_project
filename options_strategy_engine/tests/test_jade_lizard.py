from strategies.jade_lizard import create_jade_lizard


def test_jade_lizard_structure():
    strategy = create_jade_lizard(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_sell_strike=23000,
        call_sell_strike=23400,
        call_buy_strike=23600,
        quantity=75,
        put_sell_premium=120,
        call_sell_premium=100,
        call_buy_premium=40,
    )

    assert strategy.name == "Jade Lizard"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 3

    assert strategy.legs[0].strike == 23000
    assert strategy.legs[0].option_type == "PE"
    assert strategy.legs[0].position == "SELL"
    assert strategy.legs[0].quantity == 75

    assert strategy.legs[1].strike == 23400
    assert strategy.legs[1].option_type == "CE"
    assert strategy.legs[1].position == "SELL"
    assert strategy.legs[1].quantity == 75

    assert strategy.legs[2].strike == 23600
    assert strategy.legs[2].option_type == "CE"
    assert strategy.legs[2].position == "BUY"
    assert strategy.legs[2].quantity == 75


def test_jade_lizard_net_credit():
    strategy = create_jade_lizard(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_sell_strike=23000,
        call_sell_strike=23400,
        call_buy_strike=23600,
        quantity=75,
        put_sell_premium=120,
        call_sell_premium=100,
        call_buy_premium=40,
    )

    # Net premium per unit:
    # +120 + 100 - 40 = 180
    #
    # Net credit:
    # 180 × 75 = 13,500

    assert strategy.net_premium == 13500
    assert strategy.net_premium_received == 13500


def test_invalid_strike_order_rejected():
    try:
        create_jade_lizard(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_sell_strike=23400,
            call_sell_strike=23000,
            call_buy_strike=23600,
            quantity=75,
            put_sell_premium=120,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "strikes must satisfy "
            "put_sell < call_sell < call_buy"
        )


def test_equal_strikes_rejected():
    try:
        create_jade_lizard(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_sell_strike=23000,
            call_sell_strike=23000,
            call_buy_strike=23600,
            quantity=75,
            put_sell_premium=120,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "strikes must satisfy "
            "put_sell < call_sell < call_buy"
        )


def test_negative_premium_rejected():
    try:
        create_jade_lizard(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_sell_strike=23000,
            call_sell_strike=23400,
            call_buy_strike=23600,
            quantity=75,
            put_sell_premium=-10,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "option premiums cannot be negative"


def test_invalid_quantity_rejected():
    try:
        create_jade_lizard(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_sell_strike=23000,
            call_sell_strike=23400,
            call_buy_strike=23600,
            quantity=0,
            put_sell_premium=120,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "quantity must be greater than 0"
