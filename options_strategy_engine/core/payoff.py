from core.option_leg import OptionLeg
from core.strategy import Strategy


def option_intrinsic_value(
    underlying_price: float,
    strike: float,
    option_type: str,
) -> float:
    """
    Calculate option intrinsic value at expiry.

    CE = max(S - K, 0)
    PE = max(K - S, 0)
    """

    if option_type == "CE":
        return max(underlying_price - strike, 0.0)

    if option_type == "PE":
        return max(strike - underlying_price, 0.0)

    raise ValueError("option_type must be 'CE' or 'PE'")


def leg_profit_at_expiry(
    leg: OptionLeg,
    underlying_price: float,
) -> float:
    """
    Calculate profit/loss for one option leg at expiry.

    BUY:
        intrinsic value - entry premium

    SELL:
        entry premium - intrinsic value

    Result includes quantity.
    """

    intrinsic = option_intrinsic_value(
        underlying_price=underlying_price,
        strike=leg.strike,
        option_type=leg.option_type,
    )

    if leg.position == "BUY":
        profit_per_unit = intrinsic - leg.entry_premium
    else:
        profit_per_unit = leg.entry_premium - intrinsic

    return profit_per_unit * leg.quantity


def strategy_profit_at_expiry(
    strategy: Strategy,
    underlying_price: float,
) -> float:
    """
    Calculate total strategy profit/loss at expiry.
    """

    strategy.validate()

    return sum(
        leg_profit_at_expiry(
            leg=leg,
            underlying_price=underlying_price,
        )
        for leg in strategy.legs
    )

def payoff_curve(
    strategy: Strategy,
    price_range: list[float],
) -> list[tuple[float, float]]:
    """
    Generate the expiry payoff curve.

    Returns:
        [(underlying_price, profit_loss), ...]
    """
    if not price_range:
        raise ValueError("price_range cannot be empty")

    strategy.validate()

    return [
        (
            price,
            strategy_profit_at_expiry(
                strategy=strategy,
                underlying_price=price,
            ),
        )
        for price in price_range
    ]
