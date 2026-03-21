from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GymClass:
    name: str
    scheduled_at: datetime
    spots_available: int
    max_spots: int


@dataclass
class BookingGoal:
    booking_date: datetime
    name: str


@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: list[BookingGoal] = field(default_factory=list)
