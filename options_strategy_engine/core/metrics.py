from core.strategy import Strategy
from core.payoff import strategy_profit_at_expiry


def net_premium(strategy: Strategy) -> float:
    """Return net premium cash flow."""
    strategy.validate()
    return strategy.net_premium


def max_profit(
    strategy: Strategy,
    price_range: list[float],
) -> float:
    """
    Find the maximum profit across the supplied expiry prices.
    """
    if not price_range:
        raise ValueError("price_range cannot be empty")

    profits = [
        strategy_profit_at_expiry(
            strategy,
            price,
        )
        for price in price_range
    ]

    return max(profits)


def max_loss(
    strategy: Strategy,
    price_range: list[float],
) -> float:
    """
    Find the maximum loss across the supplied expiry prices.

    Returned as a negative value.
    """
    if not price_range:
        raise ValueError("price_range cannot be empty")

    profits = [
        strategy_profit_at_expiry(
            strategy,
            price,
        )
        for price in price_range
    ]

    return min(profits)


def breakeven_prices(
    strategy: Strategy,
    price_range: list[float],
) -> list[float]:
    """
    Find exact breakeven prices within the supplied price range.

    A breakeven is a price where strategy P/L equals zero.
    """
    if not price_range:
        raise ValueError("price_range cannot be empty")

    prices = sorted(set(price_range))
    breakevens = []

    for price in prices:
        profit = strategy_profit_at_expiry(
            strategy,
            price,
        )

        if profit == 0:
            breakevens.append(price)

    return breakevens


def strategy_metrics(
    strategy: Strategy,
    price_range: list[float],
) -> dict:
    """
    Return basic strategy metrics from the supplied
    expiry-price range.
    """
    strategy.validate()

    return {
        "net_premium": net_premium(strategy),
        "max_profit": max_profit(strategy, price_range),
        "max_loss": max_loss(strategy, price_range),
        "breakeven_prices": breakeven_prices(
            strategy,
            price_range,
        ),
    }
