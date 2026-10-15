from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_jade_lizard(
    index_name: str,
    expiry: str,
    put_sell_strike: float,
    call_sell_strike: float,
    call_buy_strike: float,
    quantity: int,
    put_sell_premium: float,
    call_sell_premium: float,
    call_buy_premium: float,
) -> Strategy:
    """
    Create a Jade Lizard.

    Structure:
        SELL put
        SELL lower-strike call
        BUY  higher-strike call

    Strike order:
        put_sell < call_sell < call_buy
    """

    if not (
        put_sell_strike
        < call_sell_strike
        < call_buy_strike
    ):
        raise ValueError(
            "strikes must satisfy "
            "put_sell < call_sell < call_buy"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if (
        put_sell_premium < 0
        or call_sell_premium < 0
        or call_buy_premium < 0
    ):
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Jade Lizard",
        underlying=index_name,
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=put_sell_strike,
            option_type="PE",
            position="SELL",
            quantity=quantity,
            entry_premium=put_sell_premium,
        )
    )

    strategy.add_leg(
        OptionLeg(
            index_name=index_name,
            expiry=expiry,
            strike=call_sell_strike,
            option_type="CE",
            position="SELL",
            quantity=quantity,
            entry_premium=call_sell_premium,
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
