from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_long_straddle(
    index_name: str,
    expiry: str,
    strike: float,
    quantity: int,
    call_premium: float,
    put_premium: float,
) -> Strategy:
    """
    Create a Long Straddle.

    Structure:
        BUY CE
        BUY PE

    Both options use the same strike and expiry.
    """

    if strike <= 0:
        raise ValueError(
            "strike must be greater than 0"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if call_premium < 0 or put_premium < 0:
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Long Straddle",
        underlying=index_name,
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=strike,
            option_type="CE",
            position="BUY",
            quantity=quantity,
            entry_premium=call_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=strike,
            option_type="PE",
            position="BUY",
            quantity=quantity,
            entry_premium=put_premium,
        )
    )

    strategy.validate()

    return strategy
