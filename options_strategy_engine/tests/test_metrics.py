from core.metrics import (
    net_premium,
    max_profit,
    max_loss,
    breakeven_prices,
    strategy_metrics,
)
from strategies.bull_call_spread import create_bull_call_spread


def create_test_strategy():
    return create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )


def test_net_premium():
    strategy = create_test_strategy()

    assert net_premium(strategy) == -5250


def test_max_profit():
    strategy = create_test_strategy()

    prices = list(range(23000, 24001, 10))

    assert max_profit(strategy, prices) == 9750


def test_max_loss():
    strategy = create_test_strategy()

    prices = list(range(23000, 24001, 10))

    assert max_loss(strategy, prices) == -5250


def test_breakeven():
    strategy = create_test_strategy()

    prices = list(range(23000, 24001))

    assert 23270 in breakeven_prices(strategy, prices)


def test_strategy_metrics():
    strategy = create_test_strategy()

    prices = list(range(23000, 24001, 10))

    metrics = strategy_metrics(
        strategy,
        prices,
    )

    assert metrics["net_premium"] == -5250
    assert metrics["max_profit"] == 9750
    assert metrics["max_loss"] == -5250
    assert 23270 in metrics["breakeven_prices"]

def test_bear_put_spread_metrics():
    from strategies.bear_put_spread import create_bear_put_spread

    strategy = create_bear_put_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_put_premium=80,
        higher_put_premium=150,
    )

    price_range = list(range(23000, 23601, 10))

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == -5250
    assert metrics["max_profit"] == 9750
    assert metrics["max_loss"] == -5250
    assert metrics["breakeven_prices"] == [23330]

def test_long_straddle_metrics():
    from strategies.long_straddle import create_long_straddle

    strategy = create_long_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    price_range = list(range(22000, 24401, 10))

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == -21750
    assert metrics["max_loss"] == -21750
    assert metrics["max_profit"] > 0
    assert metrics["breakeven_prices"] == [22910, 23490]

def test_short_straddle_metrics():
    from strategies.short_straddle import create_short_straddle

    strategy = create_short_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    price_range = list(range(22000, 24401, 10))

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == 21750
    assert metrics["max_profit"] == 21750
    assert metrics["breakeven_prices"] == [22910, 23490]
def test_long_strangle_metrics():
    from strategies.long_strangle import create_long_strangle

    strategy = create_long_strangle(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_strike=23000,
        call_strike=23400,
        quantity=75,
        put_premium=100,
        call_premium=120,
    )

    price_range = list(range(22000, 24401, 10))

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == -16500
    assert metrics["max_loss"] == -16500
    assert metrics["max_profit"] > 0
    assert metrics["breakeven_prices"] == [22780, 23620]
def test_short_strangle_metrics():
    from strategies.short_strangle import create_short_strangle

    strategy = create_short_strangle(
        index_name="NIFTY",
        expiry="2026-10-01",
        put_strike=23000,
        call_strike=23400,
        quantity=75,
        put_premium=100,
        call_premium=120,
    )

    price_range = list(range(22000, 24401, 10))

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == 16500
    assert metrics["max_profit"] == 16500
    assert metrics["breakeven_prices"] == [22780, 23620]
def test_long_call_butterfly_max_profit_and_loss():
    from strategies.call_butterfly import create_long_call_butterfly

    strategy = create_long_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    prices = [22800, 23000, 23200, 23400, 23600]

    metrics = strategy_metrics(strategy, prices)

    assert metrics["max_profit"] == 13500
    assert metrics["max_loss"] == -1500


def test_long_call_butterfly_breakevens():
    from strategies.call_butterfly import create_long_call_butterfly

    strategy = create_long_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    # Use a 1-point range so exact breakeven prices are included.
    prices = list(range(22900, 23501))

    metrics = strategy_metrics(strategy, prices)

    assert 23020 in metrics["breakeven_prices"]
    assert 23380 in metrics["breakeven_prices"]


def test_long_call_butterfly_net_premium():
    from strategies.call_butterfly import create_long_call_butterfly

    strategy = create_long_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    assert strategy_metrics(
        strategy,
        [23000, 23200, 23400],
    )["net_premium"] == -1500
def test_long_put_butterfly_max_profit_and_loss():
    from strategies.put_butterfly import create_long_put_butterfly

    strategy = create_long_put_butterfly(
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

    prices = [22800, 23000, 23200, 23400, 23600]

    metrics = strategy_metrics(strategy, prices)

    assert metrics["max_profit"] == 12750
    assert metrics["max_loss"] == -2250


def test_long_put_butterfly_breakevens():
    from strategies.put_butterfly import create_long_put_butterfly

    strategy = create_long_put_butterfly(
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

    # Use a 1-point range so exact breakeven prices are included.
    prices = list(range(22900, 23501))

    metrics = strategy_metrics(strategy, prices)

    assert 23030 in metrics["breakeven_prices"]
    assert 23370 in metrics["breakeven_prices"]


def test_long_put_butterfly_net_premium():
    from strategies.put_butterfly import create_long_put_butterfly

    strategy = create_long_put_butterfly(
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

    assert strategy_metrics(
        strategy,
        [23000, 23200, 23400],
    )["net_premium"] == -2250
def test_short_call_butterfly_max_profit_and_loss():
    from strategies.short_call_butterfly import create_short_call_butterfly

    strategy = create_short_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    prices = [22800, 23000, 23200, 23400, 23600]

    metrics = strategy_metrics(strategy, prices)

    assert metrics["max_profit"] == 1500
    assert metrics["max_loss"] == -13500


def test_short_call_butterfly_breakevens():
    from strategies.short_call_butterfly import create_short_call_butterfly

    strategy = create_short_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    # Net credit per unit = 20
    # Breakevens:
    # 23000 + 20 = 23020
    # 23400 - 20 = 23380

    prices = list(range(22900, 23501))

    metrics = strategy_metrics(strategy, prices)

    assert 23020 in metrics["breakeven_prices"]
    assert 23380 in metrics["breakeven_prices"]


def test_short_call_butterfly_net_premium():
    from strategies.short_call_butterfly import create_short_call_butterfly

    strategy = create_short_call_butterfly(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23000,
        middle_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=300,
        middle_call_premium=200,
        higher_call_premium=120,
    )

    assert strategy_metrics(
        strategy,
        [23000, 23200, 23400],
    )["net_premium"] == 1500
def test_short_put_butterfly_max_profit_and_loss():
    from strategies.short_put_butterfly import create_short_put_butterfly

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

    prices = [22800, 23000, 23200, 23400, 23600]

    metrics = strategy_metrics(strategy, prices)

    assert metrics["max_profit"] == 2250
    assert metrics["max_loss"] == -12750


def test_short_put_butterfly_breakevens():
    from strategies.short_put_butterfly import create_short_put_butterfly

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

    # Net credit per unit = 30
    # Breakevens:
    # 23000 + 30 = 23030
    # 23400 - 30 = 23370

    prices = list(range(22900, 23501))

    metrics = strategy_metrics(strategy, prices)

    assert 23030 in metrics["breakeven_prices"]
    assert 23370 in metrics["breakeven_prices"]


def test_short_put_butterfly_net_premium():
    from strategies.short_put_butterfly import create_short_put_butterfly

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

    assert strategy_metrics(
        strategy,
        [23000, 23200, 23400],
    )["net_premium"] == 2250
def test_iron_condor_metrics():
    from strategies.iron_condor import create_iron_condor

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

    price_range = [
        22000,
        22800,
        22900,
        23000,
        23200,
        23400,
        23500,
        23600,
        24000,
    ]

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == 7500
    assert metrics["max_profit"] == 7500
    assert metrics["max_loss"] == -7500
    assert metrics["breakeven_prices"] == [22900, 23500]


def test_iron_condor_net_credit_metric():
    from strategies.iron_condor import create_iron_condor

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

    assert net_premium(strategy) == 7500
def test_iron_butterfly_metrics():
    from strategies.iron_butterfly import create_iron_butterfly

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

    price_range = [
        22800,
        23000,
        23100,
        23200,
        23300,
        23400,
        23600,
    ]

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == 15000
    assert metrics["max_profit"] == 15000
    assert metrics["max_loss"] == 0
    assert metrics["breakeven_prices"] == [22800, 23000, 23400, 23600]


def test_iron_butterfly_net_credit_metric():
    from strategies.iron_butterfly import create_iron_butterfly

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

    assert net_premium(strategy) == 15000
def test_jade_lizard_metrics():
    from strategies.jade_lizard import create_jade_lizard

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

    price_range = [
        22000,
        22500,
        22800,
        23000,
        23200,
        23400,
        23600,
        23800,
    ]

    metrics = strategy_metrics(
        strategy,
        price_range,
    )

    assert metrics["net_premium"] == 13500
    assert metrics["max_profit"] == 13500
    assert metrics["max_loss"] == -61500
    assert metrics["breakeven_prices"] == []


def test_jade_lizard_net_credit_metric():
    from strategies.jade_lizard import create_jade_lizard

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

    assert net_premium(strategy) == 13500
