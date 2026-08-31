from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GymClass:
    name: str
    class_start: datetime
    spots_available: int
    max_spots: int


@dataclass
class BookingGoal:
    class_start: datetime
    class_name: str


class BookingSchedule(Sequence[BookingGoal]):
    """A member's booking goals, soonest first.

    Ordering is the type's job, not each repository's. Callers address goals by
    position — the number /schedule prints is the number /remove consumes — so a
    repository handing them back in storage order would silently change what a
    number means. Constructing a BookingSchedule is the only way to hold a
    member's goals, and construction sorts, so an unordered one cannot exist.

    Sorting on class_start alone leaves ties in the order given, which is the
    best available answer for two goals sharing a start time — a state aimharder
    refuses and FitBot will too.
    """

    def __init__(self, goals: Iterable[BookingGoal] = ()) -> None:
        self._goals = tuple(sorted(goals, key=lambda goal: goal.class_start))

    def __getitem__(self, index: int | slice) -> BookingGoal | tuple[BookingGoal, ...]:
        return self._goals[index]

    def __len__(self) -> int:
        return len(self._goals)

    def __eq__(self, other: object) -> bool:
        """Equal to any sequence holding the same goals in the same order.

        Callers and tests hand around plain lists of goals; comparing equal to
        one keeps them readable instead of forcing a wrapper into every
        assertion.
        """
        if isinstance(other, BookingSchedule):
            return self._goals == other._goals
        if isinstance(other, (list, tuple)):
            return list(self._goals) == list(other)
        return NotImplemented

    def __repr__(self) -> str:
        return f"BookingSchedule({list(self._goals)!r})"


@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: BookingSchedule = field(default_factory=BookingSchedule)

    def __post_init__(self) -> None:
        # Callers pass whatever they have — a list read off disk, a list built in
        # a test. Normalizing here is what makes the ordering true of every User,
        # whichever adapter built it.
        if not isinstance(self.booking_goals, BookingSchedule):
            self.booking_goals = BookingSchedule(self.booking_goals)
