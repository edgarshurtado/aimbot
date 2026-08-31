import pytest
from datetime import datetime

from domain.exceptions import UserNotFound
from domain.models import User, BookingGoal, BookingSchedule
from infrastructure.persistence.json_repository import JsonRepository


@pytest.fixture
def repository(tmp_path):
    import shutil

    src = "src/tests/test_schedule.json"
    dst = tmp_path / "test_schedule.json"
    shutil.copy(src, dst)

    repo = JsonRepository(str(dst))
    yield repo

    # Teardown: reset the file by reloading from the original template
    shutil.copy(src, dst)


# ── get_user ──────────────────────────────────────────────────────────────────


def test_get_user_returns_domain_user_object(repository):
    result = repository.get_user(66666666)
    assert isinstance(result, User)
    assert result.id == 66666666
    assert result.email == "some-email@gmail.com"
    assert result.password == "password"
    assert result.booking_goals == []


def test_get_user_returns_none_for_unknown_user(repository):
    result = repository.get_user(99999999)
    assert result is None


# ── get_all_users ─────────────────────────────────────────────────────────────


def test_get_all_users_returns_list_of_user_objects(repository):
    result = repository.get_all_users()
    assert isinstance(result, list)
    assert len(result) >= 1
    for u in result:
        assert isinstance(u, User)


# ── get_user_bookings ─────────────────────────────────────────────────────────


def test_get_user_bookings_returns_empty_list(repository):
    result = repository.get_user_bookings(66666666)
    assert result == []


def test_get_user_bookings_returns_booking_goal_objects(repository):
    goal = BookingGoal(
        class_start=datetime(2027, 1, 18, 18, 30),
        class_name="WOD",
    )
    repository.add_booking_goal(66666666, goal)

    result = repository.get_user_bookings(66666666)
    assert isinstance(result, BookingSchedule)
    assert len(result) == 1
    assert isinstance(result[0], BookingGoal)
    assert isinstance(result[0].class_start, datetime)


# ── add_booking_goal ──────────────────────────────────────────────────────────


def test_add_booking_goal_succeeds_for_known_user(repository):
    goal = BookingGoal(
        class_start=datetime(2027, 1, 18, 18, 30),
        class_name="WOD",
    )
    repository.add_booking_goal(66666666, goal)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 1
    assert bookings[0].class_name == "WOD"
    assert bookings[0].class_start == datetime(2027, 1, 18, 18, 30)


def test_add_booking_goal_fails_for_unknown_user(repository):
    goal = BookingGoal(
        class_start=datetime(2027, 1, 18, 18, 30),
        class_name="WOD",
    )
    with pytest.raises(UserNotFound):
        repository.add_booking_goal(99999999, goal)


def test_add_booking_goal_dedup_does_not_duplicate(repository):
    goal = BookingGoal(class_start=datetime(2027, 3, 15, 10, 0), class_name="OPEN")
    repository.add_booking_goal(66666666, goal)
    repository.add_booking_goal(66666666, goal)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 1


# ── remove_booking_goal ───────────────────────────────────────────────────────


def test_remove_booking_goal(repository):
    goal = BookingGoal(class_start=datetime(2027, 2, 10, 9, 0), class_name="WOD")
    repository.add_booking_goal(66666666, goal)

    repository.remove_booking_goal(66666666, goal)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 0


# ── adversarial edge cases ────────────────────────────────────────────────────


def test_dedup_does_not_fire_when_only_name_matches(repository):
    """Same name, different class_start → should NOT dedup."""
    goal1 = BookingGoal(class_start=datetime(2027, 4, 1, 10, 0), class_name="WOD")
    goal2 = BookingGoal(class_start=datetime(2027, 4, 2, 10, 0), class_name="WOD")
    repository.add_booking_goal(66666666, goal1)
    repository.add_booking_goal(66666666, goal2)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 2


def test_dedup_does_not_fire_when_only_date_matches(repository):
    """Same class_start, different name → should NOT dedup."""
    goal1 = BookingGoal(class_start=datetime(2027, 4, 1, 10, 0), class_name="WOD")
    goal2 = BookingGoal(class_start=datetime(2027, 4, 1, 10, 0), class_name="OPEN")
    repository.add_booking_goal(66666666, goal1)
    repository.add_booking_goal(66666666, goal2)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 2


def test_remove_nonexistent_goal_is_safe(repository):
    """Removing a non-existent goal should not raise."""
    repository.remove_booking_goal(
        66666666,
        BookingGoal(class_start=datetime(2099, 1, 1, 0, 0), class_name="NONEXISTENT"),
    )
    assert repository.get_user_bookings(66666666) == []


def test_get_user_returns_deep_copy(repository):
    """Mutating the returned User must not affect internal state."""
    user = repository.get_user(66666666)
    user.email = "mutated@evil.com"
    user2 = repository.get_user(66666666)
    assert user2.email == "some-email@gmail.com"


# ── booking goal ordering ─────────────────────────────────────────────────────


def _add_out_of_order(repository):
    """Three goals added back to front, so insertion order reverses the real one."""
    for class_start, class_name in [
        (datetime(2027, 6, 22, 7, 0), "WOD"),
        (datetime(2027, 6, 18, 19, 0), "Halterofilia"),
        (datetime(2027, 6, 15, 10, 0), "WOD"),
    ]:
        repository.add_booking_goal(
            66666666, BookingGoal(class_start=class_start, class_name=class_name)
        )


def test_get_user_bookings_returns_goals_soonest_first(repository):
    _add_out_of_order(repository)

    assert [g.class_start for g in repository.get_user_bookings(66666666)] == [
        datetime(2027, 6, 15, 10, 0),
        datetime(2027, 6, 18, 19, 0),
        datetime(2027, 6, 22, 7, 0),
    ]


def test_get_user_returns_goals_soonest_first(repository):
    """The bot reads goals through get_user, so this is the ordering it depends on."""
    _add_out_of_order(repository)

    assert [g.class_start for g in repository.get_user(66666666).booking_goals] == [
        datetime(2027, 6, 15, 10, 0),
        datetime(2027, 6, 18, 19, 0),
        datetime(2027, 6, 22, 7, 0),
    ]


def test_get_user_bookings_hands_back_a_schedule_that_cannot_be_reordered(repository):
    """The port promises an ordering; the type is what keeps the promise."""
    _add_out_of_order(repository)

    goals = repository.get_user_bookings(66666666)

    assert isinstance(goals, BookingSchedule)
    assert not hasattr(goals, "append")


def test_ordering_survives_a_hand_edited_file(tmp_path):
    """Entries are provisioned by hand, so the order on disk cannot be trusted."""
    import json

    dst = tmp_path / "hand_edited.json"
    dst.write_text(
        json.dumps(
            [
                {
                    "user": {"email": "a@b.com", "password": "pw", "id": 66666666},
                    "bookingGoals": [
                        {"datetime": "22-06-2027 07:00", "name": "WOD"},
                        {"datetime": "15-06-2027 10:00", "name": "WOD"},
                    ],
                }
            ]
        )
    )

    goals = JsonRepository(str(dst)).get_user_bookings(66666666)

    assert [g.class_start for g in goals] == [
        datetime(2027, 6, 15, 10, 0),
        datetime(2027, 6, 22, 7, 0),
    ]


def test_goals_sharing_a_start_time_keep_their_stored_order(repository):
    """A state aimharder refuses, so the tiebreak only has to be deterministic.

    Sorting on class_start alone leaves these in stored order; asserting it keeps
    that fallback honest rather than incidental.
    """
    for class_name in ["Halterofilia", "WOD"]:
        repository.add_booking_goal(
            66666666,
            BookingGoal(
                class_start=datetime(2027, 6, 15, 19, 0), class_name=class_name
            ),
        )

    goals = repository.get_user_bookings(66666666)

    assert [g.class_name for g in goals] == ["Halterofilia", "WOD"]


# ── serialization roundtrip ───────────────────────────────────────────────────


def test_datetime_serialization_roundtrip(tmp_path):
    import shutil

    src = "src/tests/test_schedule.json"
    dst = tmp_path / "test_schedule.json"
    shutil.copy(src, dst)

    repo1 = JsonRepository(str(dst))
    goal = BookingGoal(
        class_start=datetime(2027, 12, 25, 14, 30),
        class_name="WOD",
    )
    repo1.add_booking_goal(66666666, goal)

    # Fresh instance reads from disk
    repo2 = JsonRepository(str(dst))
    bookings = repo2.get_user_bookings(66666666)
    assert len(bookings) == 1
    assert bookings[0].class_start == datetime(2027, 12, 25, 14, 30)
    assert isinstance(bookings[0].class_start, datetime)
