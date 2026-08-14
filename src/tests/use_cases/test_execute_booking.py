import pytest
from datetime import datetime

from domain.exceptions import (
    BookingFailed,
    MESSAGE_BOX_IS_CLOSED,
    MESSAGE_GYM_CLASS_NOT_FOUND,
    UserNotFound,
)
from domain.models import BookingGoal, GymClass, User
from domain.ports.gym_client import IGymClient, IGymClientFactory
from domain.ports.notifier import IUserNotifier
from application.use_cases.execute_booking import ExecuteBookingUseCase
from tests.fakes import InMemoryBookingRepository, InMemoryUserRepository


DEFAULT_USER = User(id=123, email="a@b.com", password="pw")
DEFAULT_GOAL = BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")


@pytest.fixture
def user_repo():
    return InMemoryUserRepository(users=[DEFAULT_USER])


@pytest.fixture
def booking_repo():
    return InMemoryBookingRepository()


@pytest.fixture
def mock_client(mocker):
    return mocker.Mock(spec=IGymClient)


@pytest.fixture
def factory(mocker, mock_client):
    f = mocker.Mock(spec=IGymClientFactory)
    f.create.return_value = mock_client
    return f


@pytest.fixture
def user_notifier(mocker):
    return mocker.Mock(spec=IUserNotifier)


@pytest.fixture
def execute_uc(user_repo, booking_repo, factory, user_notifier):
    return ExecuteBookingUseCase(user_repo, booking_repo, factory, user_notifier)


def test_execute_booking_happy_path(
    execute_uc, booking_repo, mock_client, user_notifier
):
    booking_repo.add_booking_goal(DEFAULT_USER.id, DEFAULT_GOAL)

    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    ]

    execute_uc.execute(user_id=DEFAULT_USER.id, booking_goal=DEFAULT_GOAL)

    mock_client.book_class.assert_called_once_with(
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    )
    assert booking_repo.get_user_bookings(DEFAULT_USER.id) == []
    expected_msg = f"class booked for {DEFAULT_USER.email}: WOD 18:30"
    user_notifier.notify_user.assert_called_once_with(DEFAULT_USER.id, expected_msg)


def test_execute_booking_matches_by_time_and_name(
    execute_uc, booking_repo, mock_client
):
    booking_repo.add_booking_goal(DEFAULT_USER.id, DEFAULT_GOAL)

    mock_client.get_classes.return_value = [
        GymClass(
            name="OPEN",
            class_start=datetime(2027, 3, 15, 10, 0),
            spots_available=1,
            max_spots=10,
        ),
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=1,
            max_spots=10,
        ),
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 10, 0),
            spots_available=1,
            max_spots=10,
        ),
    ]

    execute_uc.execute(DEFAULT_USER.id, DEFAULT_GOAL)

    mock_client.book_class.assert_called_once_with(
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=1,
            max_spots=10,
        )
    )


def test_execute_booking_user_not_found(
    booking_repo, factory, user_notifier
):
    empty_user_repo = InMemoryUserRepository()
    uc = ExecuteBookingUseCase(empty_user_repo, booking_repo, factory, user_notifier)

    with pytest.raises(UserNotFound):
        uc.execute(999, DEFAULT_GOAL)


def test_execute_booking_no_matching_class_raises(execute_uc, mock_client):
    mock_client.get_classes.return_value = [
        GymClass(
            name="OPEN",
            class_start=datetime(2027, 3, 15, 10, 0),
            spots_available=1,
            max_spots=10,
        )
    ]

    with pytest.raises(BookingFailed, match=MESSAGE_GYM_CLASS_NOT_FOUND):
        execute_uc.execute(DEFAULT_USER.id, DEFAULT_GOAL)


def test_execute_booking_does_not_settle_for_a_name_that_merely_contains_the_goal(
    execute_uc, mock_client
):
    """A goal's class name must match the timetable's verbatim, not as a substring.

    Names are taken straight from the published Timetable now, so a goal reading
    'WOD' means the class called exactly 'WOD'. Matching on containment would book
    'WOD KIDS' whenever the box drops the plain WOD from that slot — a wrong class
    reported as a success, which is worse than not booking at all.
    """
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD KIDS",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    ]

    with pytest.raises(BookingFailed, match=MESSAGE_GYM_CLASS_NOT_FOUND):
        execute_uc.execute(DEFAULT_USER.id, DEFAULT_GOAL)

    mock_client.book_class.assert_not_called()


def test_execute_booking_box_closed(execute_uc, mock_client):
    mock_client.get_classes.return_value = []

    with pytest.raises(BookingFailed, match=MESSAGE_BOX_IS_CLOSED):
        execute_uc.execute(DEFAULT_USER.id, DEFAULT_GOAL)



def test_execute_booking_creates_client_with_user_credentials(
    booking_repo, factory, mock_client, user_notifier
):
    user = User(id=123, email="test@gym.com", password="secret123")
    user_repo = InMemoryUserRepository(users=[user])
    uc = ExecuteBookingUseCase(user_repo, booking_repo, factory, user_notifier)

    booking_repo.add_booking_goal(DEFAULT_USER.id, DEFAULT_GOAL)
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=1,
            max_spots=10,
        )
    ]

    uc.execute(DEFAULT_USER.id, DEFAULT_GOAL)

    factory.create.assert_called_once_with(
        User(id=123, email="test@gym.com", password="secret123")
    )
