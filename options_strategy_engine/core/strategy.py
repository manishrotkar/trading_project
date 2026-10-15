from dataclasses import dataclass, field

from core.option_leg import OptionLeg


@dataclass
class Strategy:
    """
    Generic multi-leg options strategy.
    """

    name: str
    underlying: str
    legs: list[OptionLeg] = field(default_factory=list)

    def add_leg(self, leg: OptionLeg) -> None:
        """Add one option leg to the strategy."""
        if leg.index_name != self.underlying:
            raise ValueError(
                "Option leg underlying does not match strategy underlying"
            )

        self.legs.append(leg)

    @property
    def leg_count(self) -> int:
        """Number of option legs."""
        return len(self.legs)

    @property
    def net_premium(self) -> float:
        """
        Net premium cash flow.

        Negative = net premium paid
        Positive = net premium received
        """
        return sum(leg.signed_premium for leg in self.legs)

    @property
    def net_premium_paid(self) -> float:
        """
        Positive value representing net premium paid.

        Returns 0 if the strategy receives a net premium.
        """
        return max(0.0, -self.net_premium)

    @property
    def net_premium_received(self) -> float:
        """
        Positive value representing net premium received.

        Returns 0 if the strategy pays a net premium.
        """
        return max(0.0, self.net_premium)

    def validate(self) -> None:
        """Validate the strategy."""
        if not self.name.strip():
            raise ValueError("Strategy name cannot be empty")

        if not self.underlying.strip():
            raise ValueError("Strategy underlying cannot be empty")

        if not self.legs:
            raise ValueError("Strategy must contain at least one option leg")
