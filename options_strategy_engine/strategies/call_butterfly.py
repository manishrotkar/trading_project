from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_long_call_butterfly(
    index_name: str,
    expiry: str,
    lower_strike: float,
    middle_strike: float,
    higher_strike: float,
    quantity: int,
    lower_call_premium: float,
    middle_call_premium: float,
    higher_call_premium: float,
) -> Strategy:
    """
    Create a Long Call Butterfly.

    Structure:
        BUY  lower-strike CE
        SELL 2 × middle-strike CE
        BUY  higher-strike CE

    The three strikes must be equally spaced.
    """

    if not (
        lower_strike < middle_strike < higher_strike
    ):
        raise ValueError(
            "strikes must satisfy lower < middle < higher"
        )

    if (
        middle_strike - lower_strike
        != higher_strike - middle_strike
    ):
        raise ValueError(
            "strikes must be equally spaced"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if (
        lower_call_premium < 0
        or middle_call_premium < 0
        or higher_call_premium < 0
    ):
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Long Call Butterfly",
        underlying=index_name,
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=lower_strike,
            option_type="CE",
            position="BUY",
            quantity=quantity,
            entry_premium=lower_call_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=middle_strike,
            option_type="CE",
            position="SELL",
            quantity=quantity * 2,
            entry_premium=middle_call_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=higher_strike,
            option_type="CE",
            position="BUY",
            quantity=quantity,
            entry_premium=higher_call_premium,
        )
    )

    strategy.validate()

    return strategy
