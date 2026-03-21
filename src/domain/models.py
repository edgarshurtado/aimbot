from dataclasses import dataclass, field
from datetime import datetime, time


@dataclass
class GymClass:
    id: str
    name: str
    start_time: time
    spots_available: int
    max_spots: int


@dataclass
class BookingGoal:
    user_id: int
    booking_date: datetime
    name: str


@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: list[BookingGoal] = field(default_factory=list)
