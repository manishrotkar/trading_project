from strategies.iron_condor import create_iron_condor


def test_iron_condor_structure():
    strategy = create_iron_condor(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_buy_strike=22800,
        put_sell_strike=23000,
        call_sell_strike=23400,
        call_buy_strike=23600,
        quantity=75,
        put_buy_premium=50,
        put_sell_premium=90,
        call_sell_premium=100,
        call_buy_premium=40,
    )

    assert strategy.name == "Iron Condor"
    assert strategy.underlying == "NIFTY"
    assert strategy.leg_count == 4

    assert strategy.legs[0].strike == 22800
    assert strategy.legs[0].option_type == "PE"
    assert strategy.legs[0].position == "BUY"
    assert strategy.legs[0].quantity == 75

    assert strategy.legs[1].strike == 23000
    assert strategy.legs[1].option_type == "PE"
    assert strategy.legs[1].position == "SELL"
    assert strategy.legs[1].quantity == 75

    assert strategy.legs[2].strike == 23400
    assert strategy.legs[2].option_type == "CE"
    assert strategy.legs[2].position == "SELL"
    assert strategy.legs[2].quantity == 75

    assert strategy.legs[3].strike == 23600
    assert strategy.legs[3].option_type == "CE"
    assert strategy.legs[3].position == "BUY"
    assert strategy.legs[3].quantity == 75


def test_iron_condor_net_credit():
    strategy = create_iron_condor(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_buy_strike=22800,
        put_sell_strike=23000,
        call_sell_strike=23400,
        call_buy_strike=23600,
        quantity=75,
        put_buy_premium=50,
        put_sell_premium=90,
        call_sell_premium=100,
        call_buy_premium=40,
    )

    # Net premium per unit:
    # -50 + 90 + 100 - 40 = 100
    #
    # Net credit:
    # 100 × 75 = 7,500

    assert strategy.net_premium == 7500
    assert strategy.net_premium_received == 7500


def test_invalid_strike_order_rejected():
    try:
        create_iron_condor(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=23000,
            put_sell_strike=22800,
            call_sell_strike=23400,
            call_buy_strike=23600,
            quantity=75,
            put_buy_premium=50,
            put_sell_premium=90,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "strikes must satisfy "
            "put_buy < put_sell < call_sell < call_buy"
        )


def test_equal_strikes_rejected():
    try:
        create_iron_condor(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=22800,
            put_sell_strike=23000,
            call_sell_strike=23000,
            call_buy_strike=23600,
            quantity=75,
            put_buy_premium=50,
            put_sell_premium=90,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "strikes must satisfy "
            "put_buy < put_sell < call_sell < call_buy"
        )


def test_negative_premium_rejected():
    try:
        create_iron_condor(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=22800,
            put_sell_strike=23000,
            call_sell_strike=23400,
            call_buy_strike=23600,
            quantity=75,
            put_buy_premium=-10,
            put_sell_premium=90,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "option premiums cannot be negative"


def test_invalid_quantity_rejected():
    try:
        create_iron_condor(
            index_name="NIFTY",
            expiry="2026-10-01",
            put_buy_strike=22800,
            put_sell_strike=23000,
            call_sell_strike=23400,
            call_buy_strike=23600,
            quantity=0,
            put_buy_premium=50,
            put_sell_premium=90,
            call_sell_premium=100,
            call_buy_premium=40,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "quantity must be greater than 0"
