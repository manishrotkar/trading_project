from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_iron_butterfly(
    index_name: str,
    expiry: str,
    put_buy_strike: float,
    middle_strike: float,
    call_buy_strike: float,
    quantity: int,
    put_buy_premium: float,
    middle_put_premium: float,
    middle_call_premium: float,
    call_buy_premium: float,
) -> Strategy:
    """
    Create an Iron Butterfly.

    Structure:
        BUY  lower-strike PE
        SELL middle-strike PE
        SELL middle-strike CE
        BUY  higher-strike CE

    Strike order:
        put_buy < middle < call_buy
    """

    if not (
        put_buy_strike
        < middle_strike
        < call_buy_strike
    ):
        raise ValueError(
            "strikes must satisfy "
            "put_buy < middle < call_buy"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if (
        put_buy_premium < 0
        or middle_put_premium < 0
        or middle_call_premium < 0
        or call_buy_premium < 0
    ):
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Iron Butterfly",
        underlying=index_name,
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=put_buy_strike,
            option_type="PE",
            position="BUY",
            quantity=quantity,
            entry_premium=put_buy_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=middle_strike,
            option_type="PE",
            position="SELL",
            quantity=quantity,
            entry_premium=middle_put_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=middle_strike,
            option_type="CE",
            position="SELL",
            quantity=quantity,
            entry_premium=middle_call_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=call_buy_strike,
            option_type="CE",
            position="BUY",
            quantity=quantity,
            entry_premium=call_buy_premium,
        )
    )

    strategy.validate()

    return strategy
