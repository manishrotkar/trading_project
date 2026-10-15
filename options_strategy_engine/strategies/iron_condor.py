from core.option_leg import OptionLeg
from core.strategy import Strategy


def create_iron_condor(
    index_name: str,
    expiry: str,
    put_buy_strike: float,
    put_sell_strike: float,
    call_sell_strike: float,
    call_buy_strike: float,
    quantity: int,
    put_buy_premium: float,
    put_sell_premium: float,
    call_sell_premium: float,
    call_buy_premium: float,
) -> Strategy:
    """
    Create an Iron Condor.

    Structure:
        BUY  lower-strike PE
        SELL higher-strike PE
        SELL lower-strike CE
        BUY  higher-strike CE

    Strike order:
        put_buy < put_sell < call_sell < call_buy
    """

    if not (
        put_buy_strike
        < put_sell_strike
        < call_sell_strike
        < call_buy_strike
    ):
        raise ValueError(
            "strikes must satisfy "
            "put_buy < put_sell < call_sell < call_buy"
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than 0"
        )

    if (
        put_buy_premium < 0
        or put_sell_premium < 0
        or call_sell_premium < 0
        or call_buy_premium < 0
    ):
        raise ValueError(
            "option premiums cannot be negative"
        )

    strategy = Strategy(
        name="Iron Condor",
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
