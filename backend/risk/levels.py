from enum import IntEnum


class Level(IntEnum):
    """A risk level. Ordered, so `max()` is the worst; the integer is what mean level averages."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()
