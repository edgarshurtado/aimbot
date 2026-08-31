"""BookingSchedule is the ordering promise made unbreakable.

The bot numbers a member's goals by position — /schedule prints the number that
/remove consumes — so these tests pin the order down at the type, where no
repository can get it wrong.
"""

from datetime import datetime

import pytest

from domain.models import BookingGoal, BookingSchedule, User

EARLIEST = BookingGoal(class_start=datetime(2027, 6, 15, 10, 0), class_name="WOD")
MIDDLE = BookingGoal(
    class_start=datetime(2027, 6, 18, 19, 0), class_name="Halterofilia"
)
LATEST = BookingGoal(class_start=datetime(2027, 6, 22, 7, 0), class_name="WOD")


def test_sorts_goals_soonest_first():
    schedule = BookingSchedule([LATEST, EARLIEST, MIDDLE])

    assert list(schedule) == [EARLIEST, MIDDLE, LATEST]


def test_is_empty_by_default():
    assert len(BookingSchedule()) == 0
    assert not BookingSchedule()


def test_goals_sharing_a_start_time_keep_the_order_given():
    """A tie is a state aimharder refuses; stored order is the best answer left."""
    first = BookingGoal(class_start=datetime(2027, 6, 15, 10, 0), class_name="WOD")
    second = BookingGoal(
        class_start=datetime(2027, 6, 15, 10, 0), class_name="Halterofilia"
    )

    assert list(BookingSchedule([first, second])) == [first, second]
    assert list(BookingSchedule([second, first])) == [second, first]


def test_reads_like_the_list_it_replaces():
    schedule = BookingSchedule([LATEST, EARLIEST])

    assert len(schedule) == 2
    assert schedule[0] == EARLIEST
    assert EARLIEST in schedule
    assert [goal for goal in schedule] == [EARLIEST, LATEST]
    assert list(enumerate(schedule)) == [(0, EARLIEST), (1, LATEST)]


def test_equals_a_sequence_holding_the_same_goals_in_order():
    schedule = BookingSchedule([LATEST, EARLIEST])

    assert schedule == [EARLIEST, LATEST]
    assert [EARLIEST, LATEST] == schedule
    assert schedule == (EARLIEST, LATEST)
    assert schedule == BookingSchedule([EARLIEST, LATEST])
    assert BookingSchedule() == []


def test_differs_from_a_sequence_holding_other_goals():
    schedule = BookingSchedule([EARLIEST])

    assert schedule != [MIDDLE]
    assert schedule != [EARLIEST, MIDDLE]
    assert schedule != "not a sequence of goals"


def test_cannot_be_reordered_after_construction():
    """No mutator means no way back to an unordered collection."""
    schedule = BookingSchedule([EARLIEST, LATEST])

    assert not hasattr(schedule, "append")
    assert not hasattr(schedule, "sort")
    with pytest.raises(TypeError):
        schedule[0] = MIDDLE


def test_a_copy_of_the_goals_survives_the_caller_mutating_theirs():
    goals = [LATEST, EARLIEST]
    schedule = BookingSchedule(goals)

    goals.clear()

    assert list(schedule) == [EARLIEST, LATEST]


# ── User ──────────────────────────────────────────────────────────────────────


def test_user_orders_the_goals_it_is_handed():
    """Any adapter building a User gets the ordering for free."""
    user = User(id=1, email="a@b.com", password="pw", booking_goals=[LATEST, EARLIEST])

    assert list(user.booking_goals) == [EARLIEST, LATEST]


def test_user_without_goals_has_an_empty_schedule():
    user = User(id=1, email="a@b.com", password="pw")

    assert user.booking_goals == []
    assert isinstance(user.booking_goals, BookingSchedule)


def test_reassigning_booking_goals_after_construction_still_orders_them():
    """The guarantee holds at every assignment, not just at __init__."""
    user = User(id=1, email="a@b.com", password="pw")

    user.booking_goals = [LATEST, EARLIEST]

    assert isinstance(user.booking_goals, BookingSchedule)
    assert list(user.booking_goals) == [EARLIEST, LATEST]
