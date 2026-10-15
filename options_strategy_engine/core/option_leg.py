from dataclasses import dataclass
from typing import Literal


OptionType = Literal["CE", "PE"]
PositionType = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class OptionLeg:
    """
    Represents one option leg in an options strategy.
    """

    index_name: str
    expiry: str
    strike: float
    option_type: OptionType
    position: PositionType
    quantity: int
    entry_premium: float

    def __post_init__(self):
        if self.option_type not in ("CE", "PE"):
            raise ValueError("option_type must be 'CE' or 'PE'")

        if self.position not in ("BUY", "SELL"):
            raise ValueError("position must be 'BUY' or 'SELL'")

        if self.strike <= 0:
            raise ValueError("strike must be greater than 0")

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than 0")

        if self.entry_premium < 0:
            raise ValueError("entry_premium cannot be negative")

    @property
    def signed_premium(self) -> float:
        """
        Premium from the strategy's perspective.

        BUY  -> negative cash flow
        SELL -> positive cash flow
        """
        multiplier = -1 if self.position == "BUY" else 1
        return multiplier * self.entry_premium * self.quantity

    @property
    def premium_value(self) -> float:
        """
        Absolute premium value for this leg.
        """
        return self.entry_premium * self.quantity
