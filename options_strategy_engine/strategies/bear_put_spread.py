from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_bear_put_spread(
    index_name: str,
    expiry: str,
    lower_strike: float,
    higher_strike: float,
    quantity: int,
    lower_put_premium: float,
    higher_put_premium: float,
) -> Strategy:
    """
    Create a Bear Put Spread.

    Structure:
        BUY  higher-strike PE
        SELL lower-strike PE
    """

    if lower_strike >= higher_strike:
        raise ValueError(
            "lower_strike must be less than higher_strike"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if lower_put_premium < 0 or higher_put_premium < 0:
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Bear Put Spread",
        underlying=index_name,
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=higher_strike,
            option_type="PE",
            position="BUY",
            quantity=quantity,
            entry_premium=higher_put_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=lower_strike,
            option_type="PE",
            position="SELL",
            quantity=quantity,
            entry_premium=lower_put_premium,
        )
    )

    strategy.validate()

    return strategy
