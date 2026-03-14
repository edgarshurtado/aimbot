import pytest
from datetime import datetime

from domain.models import User, BookingGoal
from error_handling import UserNotFound
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
        booking_date=datetime(2027, 1, 18, 18, 30),
        name="WOD",
        job_id="test-job-1",
    )
    repository.add_booking_goal(66666666, goal)

    result = repository.get_user_bookings(66666666)
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], BookingGoal)
    assert isinstance(result[0].booking_date, datetime)


# ── add_booking_goal ──────────────────────────────────────────────────────────

def test_add_booking_goal_succeeds_for_known_user(repository):
    goal = BookingGoal(
        booking_date=datetime(2027, 1, 18, 18, 30),
        name="WOD",
        job_id="test-job-1",
    )
    result = repository.add_booking_goal(66666666, goal)
    assert result.success is True

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 1
    assert bookings[0].name == "WOD"
    assert bookings[0].booking_date == datetime(2027, 1, 18, 18, 30)
    assert bookings[0].job_id == "test-job-1"


def test_add_booking_goal_fails_for_unknown_user(repository):
    goal = BookingGoal(
        booking_date=datetime(2027, 1, 18, 18, 30),
        name="WOD",
        job_id="test-job-x",
    )
    result = repository.add_booking_goal(99999999, goal)
    assert result.success is False
    assert isinstance(result.error, UserNotFound)


def test_add_booking_goal_dedup_updates_job_id(repository):
    goal1 = BookingGoal(
        booking_date=datetime(2027, 3, 15, 10, 0),
        name="OPEN",
        job_id="old-job",
    )
    repository.add_booking_goal(66666666, goal1)

    goal2 = BookingGoal(
        booking_date=datetime(2027, 3, 15, 10, 0),
        name="OPEN",
        job_id="new-job",
    )
    repository.add_booking_goal(66666666, goal2)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 1
    assert bookings[0].job_id == "new-job"


# ── remove_booking_goal ───────────────────────────────────────────────────────

def test_remove_booking_goal(repository):
    goal = BookingGoal(
        booking_date=datetime(2027, 2, 10, 9, 0),
        name="WOD",
        job_id="to-remove",
    )
    repository.add_booking_goal(66666666, goal)

    repository.remove_booking_goal(66666666, "to-remove")

    bookings = repository.get_user_bookings(66666666)
    assert all(b.job_id != "to-remove" for b in bookings)


# ── find_booking_goal ─────────────────────────────────────────────────────────

def test_find_booking_goal_found(repository):
    goal = BookingGoal(
        booking_date=datetime(2027, 5, 20, 9, 0),
        name="WOD",
        job_id="find-me",
    )
    repository.add_booking_goal(66666666, goal)

    result = repository.find_booking_goal(66666666, datetime(2027, 5, 20, 9, 0), "WOD")
    assert result is not None
    assert isinstance(result, BookingGoal)
    assert result.job_id == "find-me"


def test_find_booking_goal_not_found(repository):
    result = repository.find_booking_goal(66666666, datetime(2099, 1, 1, 0, 0), "NONEXISTENT")
    assert result is None


# ── adversarial edge cases ────────────────────────────────────────────────────

def test_dedup_does_not_fire_when_only_name_matches(repository):
    """Same name, different booking_date → should NOT dedup."""
    goal1 = BookingGoal(booking_date=datetime(2027, 4, 1, 10, 0), name="WOD", job_id="job-a")
    goal2 = BookingGoal(booking_date=datetime(2027, 4, 2, 10, 0), name="WOD", job_id="job-b")
    repository.add_booking_goal(66666666, goal1)
    repository.add_booking_goal(66666666, goal2)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 2


def test_dedup_does_not_fire_when_only_date_matches(repository):
    """Same booking_date, different name → should NOT dedup."""
    goal1 = BookingGoal(booking_date=datetime(2027, 4, 1, 10, 0), name="WOD", job_id="job-a")
    goal2 = BookingGoal(booking_date=datetime(2027, 4, 1, 10, 0), name="OPEN", job_id="job-b")
    repository.add_booking_goal(66666666, goal1)
    repository.add_booking_goal(66666666, goal2)

    bookings = repository.get_user_bookings(66666666)
    assert len(bookings) == 2


def test_remove_nonexistent_job_id_is_safe(repository):
    """Removing a non-existent job_id should not raise."""
    repository.remove_booking_goal(66666666, "does-not-exist")
    assert repository.get_user_bookings(66666666) == []


def test_get_user_returns_deep_copy(repository):
    """Mutating the returned User must not affect internal state."""
    user = repository.get_user(66666666)
    user.email = "mutated@evil.com"
    user2 = repository.get_user(66666666)
    assert user2.email == "some-email@gmail.com"


# ── serialization roundtrip ───────────────────────────────────────────────────

def test_datetime_serialization_roundtrip(tmp_path):
    import shutil

    src = "src/tests/test_schedule.json"
    dst = tmp_path / "test_schedule.json"
    shutil.copy(src, dst)

    repo1 = JsonRepository(str(dst))
    goal = BookingGoal(
        booking_date=datetime(2027, 12, 25, 14, 30),
        name="WOD",
        job_id="roundtrip-job",
    )
    repo1.add_booking_goal(66666666, goal)

    # Fresh instance reads from disk
    repo2 = JsonRepository(str(dst))
    bookings = repo2.get_user_bookings(66666666)
    assert len(bookings) == 1
    assert bookings[0].booking_date == datetime(2027, 12, 25, 14, 30)
    assert isinstance(bookings[0].booking_date, datetime)
