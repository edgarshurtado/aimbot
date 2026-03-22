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


@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: list[BookingGoal] = field(default_factory=list)
