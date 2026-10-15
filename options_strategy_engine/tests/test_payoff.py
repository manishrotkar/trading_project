from core.payoff import (
    option_intrinsic_value,
    leg_profit_at_expiry,
    strategy_profit_at_expiry,
    payoff_curve,
)

from core.option_leg import OptionLeg
from strategies.bull_call_spread import create_bull_call_spread

def test_payoff_curve():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    prices = [23000, 23200, 23270, 23400, 24000]

    curve = payoff_curve(
        strategy=strategy,
        price_range=prices,
    )

    assert curve == [
        (23000, -5250),
        (23200, -5250),
        (23270, 0),
        (23400, 9750),
        (24000, 9750),
    ]

def test_call_intrinsic_value():
    assert option_intrinsic_value(
        underlying_price=23300,
        strike=23200,
        option_type="CE",
    ) == 100

    assert option_intrinsic_value(
        underlying_price=23100,
        strike=23200,
        option_type="CE",
    ) == 0


def test_put_intrinsic_value():
    assert option_intrinsic_value(
        underlying_price=23100,
        strike=23200,
        option_type="PE",
    ) == 100

    assert option_intrinsic_value(
        underlying_price=23300,
        strike=23200,
        option_type="PE",
    ) == 0


def test_buy_call_profit():
    leg = OptionLeg(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        option_type="CE",
        position="BUY",
        quantity=75,
        entry_premium=150,
    )

    # Intrinsic = 100
    # Profit = (100 - 150) * 75
    assert leg_profit_at_expiry(
        leg=leg,
        underlying_price=23300,
    ) == -3750


def test_sell_call_profit():
    leg = OptionLeg(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23400,
        option_type="CE",
        position="SELL",
        quantity=75,
        entry_premium=80,
    )

    # Intrinsic = 0
    # Profit = (80 - 0) * 75
    assert leg_profit_at_expiry(
        leg=leg,
        underlying_price=23300,
    ) == 6000


def test_bull_call_spread_profit():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    # At NIFTY = 23300:
    #
    # BUY 23200 CE:
    # (100 - 150) * 75 = -3750
    #
    # SELL 23400 CE:
    # (80 - 0) * 75 = +6000
    #
    # Total = +2250

    assert strategy_profit_at_expiry(
        strategy=strategy,
        underlying_price=23300,
    ) == 2250


def test_bull_call_spread_max_loss():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    # Below lower strike both options expire worthless.
    # Maximum loss = net debit = 5250.

    assert strategy_profit_at_expiry(
        strategy=strategy,
        underlying_price=23000,
    ) == -5250


def test_bull_call_spread_max_profit():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    # Maximum intrinsic spread value:
    # 23400 - 23200 = 200
    #
    # Net debit = 150 - 80 = 70
    #
    # Maximum profit per unit = 200 - 70 = 130
    # Maximum profit = 130 * 75 = 9750

    assert strategy_profit_at_expiry(
        strategy=strategy,
        underlying_price=24000,
    ) == 9750


def test_bull_call_spread_breakeven():
    strategy = create_bull_call_spread(
        index_name="NIFTY",
        expiry="2026-10-01",
        lower_strike=23200,
        higher_strike=23400,
        quantity=75,
        lower_call_premium=150,
        higher_call_premium=80,
    )

    # Breakeven = lower strike + net debit
    #
    # = 23200 + 70
    # = 23270

    assert strategy_profit_at_expiry(
        strategy=strategy,
        underlying_price=23270,
    ) == 0

def test_bear_put_spread_max_loss():
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

    # Net debit = 70 × 75 = 5,250
    assert strategy_profit_at_expiry(
        strategy,
        24000,
    ) == -5250


def test_bear_put_spread_max_profit():
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

    # Strike width = 200
    # Maximum profit = (200 - 70) × 75 = 9,750
    assert strategy_profit_at_expiry(
        strategy,
        23000,
    ) == 9750

def test_long_straddle_max_loss():
    from strategies.long_straddle import create_long_straddle

    strategy = create_long_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # Maximum loss occurs at the strike.
    # Total premium = 290 × 75 = 21,750

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == -21750


def test_long_straddle_profit_below_strike():
    from strategies.long_straddle import create_long_straddle

    strategy = create_long_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # At 22,000:
    # PE intrinsic = 1,200
    # Profit per unit = 1,200 - 290 = 910
    # Profit = 910 × 75 = 68,250

    assert strategy_profit_at_expiry(
        strategy,
        22000,
    ) == 68250


def test_long_straddle_profit_above_strike():
    from strategies.long_straddle import create_long_straddle

    strategy = create_long_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # At 24,000:
    # CE intrinsic = 800
    # Profit per unit = 800 - 290 = 510
    # Profit = 510 × 75 = 38,250

    assert strategy_profit_at_expiry(
        strategy,
        24000,
    ) == 38250
def test_short_straddle_max_profit():
    from strategies.short_straddle import create_short_straddle

    strategy = create_short_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # Maximum profit occurs at the strike.
    # Total premium received = 290 × 75 = 21,750

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 21750


def test_short_straddle_loss_below_strike():
    from strategies.short_straddle import create_short_straddle

    strategy = create_short_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # At 22,000:
    # PE intrinsic = 1,200
    # Profit per unit = 290 - 1,200 = -910
    # Loss = -910 × 75 = -68,250

    assert strategy_profit_at_expiry(
        strategy,
        22000,
    ) == -68250


def test_short_straddle_loss_above_strike():
    from strategies.short_straddle import create_short_straddle

    strategy = create_short_straddle(
        index_name="NIFTY",
        expiry="2026-10-01",
        strike=23200,
        quantity=75,
        call_premium=150,
        put_premium=140,
    )

    # At 24,000:
    # CE intrinsic = 800
    # Profit per unit = 290 - 800 = -510
    # Loss = -510 × 75 = -38,250

    assert strategy_profit_at_expiry(
        strategy,
        24000,
    ) == -38250
def test_long_strangle_max_loss():
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

    # Maximum loss occurs between the two strikes.
    # Total premium = 220 × 75 = 16,500

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == -16500


def test_long_strangle_profit_below_put_strike():
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

    # At 22,000:
    # PE intrinsic = 1,000
    # Profit per unit = 1,000 - 220 = 780
    # Profit = 780 × 75 = 58,500

    assert strategy_profit_at_expiry(
        strategy,
        22000,
    ) == 58500


def test_long_strangle_profit_above_call_strike():
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

    # At 24000:
    # CE intrinsic = 600
    # Profit per unit = 600 - 220 = 380
    # Profit = 380 × 75 = 28,500

    assert strategy_profit_at_expiry(
        strategy,
        24000,
    ) == 28500
def test_short_strangle_max_profit():
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

    # Maximum profit occurs between the two strikes.
    # Total premium received = 220 × 75 = 16,500

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 16500


def test_short_strangle_loss_below_put_strike():
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

    # At 22,000:
    # PE intrinsic = 1,000
    # Profit per unit = 220 - 1,000 = -780
    # Loss = -780 × 75 = -58,500

    assert strategy_profit_at_expiry(
        strategy,
        22000,
    ) == -58500


def test_short_strangle_loss_above_call_strike():
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

    # At 24,000:
    # CE intrinsic = 600
    # Profit per unit = 220 - 600 = -380
    # Loss = -380 × 75 = -28,500

    assert strategy_profit_at_expiry(
        strategy,
        24000,
    ) == -28500
def test_long_call_butterfly_max_loss():
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

    # Net debit = 20 × 75 = 1,500
    # Maximum loss occurs outside the butterfly range.

    assert strategy_profit_at_expiry(
        strategy,
        22800,
    ) == -1500


def test_long_call_butterfly_max_profit():
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

    # Maximum profit occurs at the middle strike.
    #
    # Strike width = 200
    # Net debit = 20
    # Maximum profit = (200 - 20) × 75
    #                = 13,500

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 13500


def test_long_call_butterfly_upper_loss():
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

    # Maximum loss also occurs above the upper strike.

    assert strategy_profit_at_expiry(
        strategy,
        23600,
    ) == -1500
def test_long_put_butterfly_max_loss():
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

    assert strategy_profit_at_expiry(
        strategy,
        23600,
    ) == -2250


def test_long_put_butterfly_max_profit():
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

    # Strike width = 200
    # Net debit = 30
    # Maximum profit = (200 - 30) × 75
    #                = 12,750

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 12750


def test_long_put_butterfly_lower_loss():
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

    assert strategy_profit_at_expiry(
        strategy,
        22800,
    ) == -2250
def test_short_call_butterfly_max_profit():
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

    # Maximum profit = net credit = 1,500

    assert strategy_profit_at_expiry(
        strategy,
        22800,
    ) == 1500


def test_short_call_butterfly_max_loss():
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

    # Strike width = 200
    # Net credit = 20
    # Maximum loss = (200 - 20) × 75
    #              = 13,500

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == -13500


def test_short_call_butterfly_upper_profit():
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

    assert strategy_profit_at_expiry(
        strategy,
        23600,
    ) == 1500
def test_short_put_butterfly_max_profit():
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

    # Maximum profit = net credit = 2,250

    assert strategy_profit_at_expiry(
        strategy,
        23600,
    ) == 2250


def test_short_put_butterfly_max_loss():
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

    # Strike width = 200
    # Net credit = 30
    # Maximum loss = (200 - 30) × 75
    #              = 12,750

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == -12750


def test_short_put_butterfly_lower_profit():
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

    assert strategy_profit_at_expiry(
        strategy,
        22800,
    ) == 2250
def test_iron_condor_max_profit():
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

    # Maximum profit = net credit = ₹7,500

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 7500


def test_iron_condor_max_loss():
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

    # Both wings are 200 points wide.
    # Net credit = 100 points.
    # Maximum loss = (200 - 100) × 75
    #              = ₹7,500

    assert strategy_profit_at_expiry(
        strategy,
        22600,
    ) == -7500


def test_iron_condor_upper_max_loss():
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

    assert strategy_profit_at_expiry(
        strategy,
        23800,
    ) == -7500
def test_iron_butterfly_max_profit():
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

    # Maximum profit = net credit = ₹15,000
    # Maximum profit occurs at the middle strike.

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 15000


def test_iron_butterfly_lower_max_loss():
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

    # Put wing width = 200
    # Net credit = 200
    # Maximum loss = (200 - 200) × 75 = ₹0
    #
    # Therefore this particular premium example has
    # zero loss at the lower wing.

    assert strategy_profit_at_expiry(
        strategy,
        23000,
    ) == 0


def test_iron_butterfly_upper_max_loss():
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

    # Call wing width = 200
    # Net credit = 200
    # Maximum loss = (200 - 200) × 75 = ₹0

    assert strategy_profit_at_expiry(
        strategy,
        23400,
    ) == 0
def test_jade_lizard_max_profit():
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

    # Maximum profit = net credit
    # = 180 × 75 = ₹13,500

    assert strategy_profit_at_expiry(
        strategy,
        23200,
    ) == 13500


def test_jade_lizard_lower_side_loss():
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

    # At 22,800:
    # Short 23,000 PE intrinsic = 200
    # Net credit = 180
    # Loss = (200 - 180) × 75 = ₹1,500

    assert strategy_profit_at_expiry(
        strategy,
        22800,
    ) == -1500


def test_jade_lizard_upper_side_loss():
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

    # At 23,800:
    # Call spread loss = 400 - 200 = 200
    # Net credit = 180
    # Net loss = 20 × 75 = ₹1,500

    assert strategy_profit_at_expiry(
        strategy,
        23800,
    ) == -1500
