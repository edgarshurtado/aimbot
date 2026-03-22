import copy
import json
import os
from datetime import datetime

from domain.models import User, BookingGoal
from domain.ports.booking_repository import IBookingRepository
from domain.ports.user_repository import IUserRepository
from error_handling import Result, UserNotFound


class JsonRepository(IUserRepository, IBookingRepository):
    _DATETIME_FMT = "%d-%m-%Y %H:%M"

    def __init__(self, db_file_name: str = "schedule.json") -> None:
        self._db_file_name = db_file_name
        self._data = self._load()

    def _file_path(self) -> str:
        # If db_file_name is absolute, use it directly.
        if os.path.isabs(self._db_file_name):
            return self._db_file_name
        # Resolve relative to src/ directory (two levels up from this file).
        src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(src_dir, self._db_file_name)

    def _load(self) -> list:
        with open(self._file_path(), "r") as f:
            return json.load(f)

    def _save(self) -> None:
        with open(self._file_path(), "w", encoding="utf-8") as f:
            f.write(json.dumps(self._data, indent=4))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _find_raw_user(self, user_id: int) -> dict | None:
        return next((d for d in self._data if d["user"]["id"] == user_id), None)

    def _raw_to_booking_goal(self, raw: dict) -> BookingGoal:
        return BookingGoal(
            class_start=datetime.strptime(raw["datetime"], self._DATETIME_FMT),
            name=raw["name"],
        )

    def _booking_goal_to_raw(self, goal: BookingGoal) -> dict:
        return {
            "datetime": goal.class_start.strftime(self._DATETIME_FMT),
            "name": goal.name,
        }

    def _raw_to_user(self, raw_entry: dict) -> User:
        raw_user = raw_entry["user"]
        booking_goals = [
            self._raw_to_booking_goal(bg) for bg in raw_entry.get("bookingGoals", [])
        ]
        return User(
            id=raw_user["id"],
            email=raw_user["email"],
            password=raw_user["password"],
            booking_goals=booking_goals,
        )

    # ── IUserRepository ───────────────────────────────────────────────────────

    def get_user(self, user_id: int) -> User | None:
        raw = self._find_raw_user(user_id)
        if raw is None:
            return None
        return copy.deepcopy(self._raw_to_user(raw))

    def get_all_users(self) -> list[User]:
        return [self._raw_to_user(entry) for entry in self._data]

    # ── IBookingRepository ────────────────────────────────────────────────────

    def get_user_bookings(self, user_id: int) -> list[BookingGoal]:
        raw = self._find_raw_user(user_id)
        if raw is None:
            return []
        return [self._raw_to_booking_goal(bg) for bg in raw.get("bookingGoals", [])]

    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> Result:
        raw = self._find_raw_user(user_id)
        if raw is None:
            return Result(success=False, error=UserNotFound())

        goals_list = raw.setdefault("bookingGoals", [])

        # Dedup: if a goal with the same (class_start, name) exists, keep it as-is
        raw_goal = self._booking_goal_to_raw(goal)
        for existing in goals_list:
            if (existing["datetime"] == raw_goal["datetime"]
                    and existing["name"] == raw_goal["name"]):
                self._save()
                return Result(success=True)

        goals_list.append(raw_goal)
        self._save()
        return Result(success=True)

    def remove_booking_goal(self, user_id: int, class_start: datetime, class_name: str) -> None:
        raw = self._find_raw_user(user_id)
        if raw is None:
            return
        date_str = class_start.strftime(self._DATETIME_FMT)
        raw["bookingGoals"] = [
            bg for bg in raw.get("bookingGoals", [])
            if not (bg["datetime"] == date_str and bg["name"] == class_name)
        ]
        self._save()
