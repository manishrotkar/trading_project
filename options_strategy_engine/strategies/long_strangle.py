from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_long_strangle(
    index_name: str,
    expiry: str,
    put_strike: float,
    call_strike: float,
    quantity: int,
    put_premium: float,
    call_premium: float,
) -> Strategy:
    """
    Create a Long Strangle.

    Structure:
        BUY OTM PE
        BUY OTM CE

    The put strike must be lower than the call strike.
    """

    if put_strike >= call_strike:
        raise ValueError(
            "put_strike must be less than call_strike"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if put_premium < 0 or call_premium < 0:
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Long Strangle",
        underlying=index_name,
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=put_strike,
            option_type="PE",
            position="BUY",
            quantity=quantity,
            entry_premium=put_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=call_strike,
            option_type="CE",
            position="BUY",
            quantity=quantity,
            entry_premium=call_premium,
        )
    )

    strategy.validate()

    return strategy
