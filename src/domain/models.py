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
    booking_date: datetime   # renamed from 'datetime' to avoid shadowing
    name: str


@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: list[BookingGoal] = field(default_factory=list)
