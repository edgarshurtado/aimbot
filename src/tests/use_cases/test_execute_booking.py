import pytest
from datetime import datetime

from domain.exceptions import BookingFailed, UserNotFound
from domain.models import BookingGoal, GymClass, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_client import IGymClient, IGymClientFactory
from domain.ports.notifier import IUserNotifier
from domain.ports.user_repository import IUserRepository
from application.use_cases.execute_booking import ExecuteBookingUseCase


@pytest.fixture
def user_repo(mocker):
    return mocker.Mock(spec=IUserRepository)


@pytest.fixture
def booking_repo(mocker):
    return mocker.Mock(spec=IBookingRepository)


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


def _make_user(user_id=123, email="a@b.com", password="pw"):
    return User(id=user_id, email=email, password=password)


def _make_goal():
    return BookingGoal(class_start=datetime(2027, 3, 15, 18, 30), class_name="WOD")


def test_execute_booking_happy_path(
    execute_uc, user_repo, booking_repo, mock_client, user_notifier
):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user(user_id=123)
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    ]

    execute_uc.execute(user_id=123, booking_goal=goal)

    mock_client.book_class.assert_called_once_with(
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    )
    booking_repo.remove_booking_goal.assert_called_once_with(123, goal)
    expected_msg = "class booked for a@b.com: WOD 18:30"
    user_notifier.notify_user.assert_called_once_with(123, expected_msg)


def test_execute_booking_matches_by_time_and_name(
    execute_uc, user_repo, mock_client
):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user()
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

    execute_uc.execute(123, goal)

    mock_client.book_class.assert_called_once_with(
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=1,
            max_spots=10,
        )
    )


def test_execute_booking_user_not_found(execute_uc, user_repo, factory):
    goal = _make_goal()

    user_repo.get_user.return_value = None

    with pytest.raises(UserNotFound):
        execute_uc.execute(999, goal)

    factory.create.assert_not_called()


def test_execute_booking_no_matching_class_raises(execute_uc, user_repo, mock_client):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user()
    mock_client.get_classes.return_value = [
        GymClass(
            name="OPEN",
            class_start=datetime(2027, 3, 15, 10, 0),
            spots_available=1,
            max_spots=10,
        )
    ]

    with pytest.raises(BookingFailed):
        execute_uc.execute(123, goal)


def test_execute_booking_box_closed(execute_uc, user_repo, mock_client):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user()
    mock_client.get_classes.return_value = []

    with pytest.raises(BookingFailed):
        execute_uc.execute(123, goal)


def test_execute_booking_cleans_up_goal(
    execute_uc, user_repo, booking_repo, mock_client
):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user()
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    ]

    execute_uc.execute(123, goal)

    booking_repo.remove_booking_goal.assert_called_once_with(123, goal)


def test_execute_booking_notifies_user(
    execute_uc, user_repo, mock_client, user_notifier
):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user(user_id=123)
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=5,
            max_spots=20,
        )
    ]

    execute_uc.execute(123, goal)

    expected_msg = "class booked for a@b.com: WOD 18:30"
    user_notifier.notify_user.assert_called_once_with(123, expected_msg)


def test_execute_booking_uses_class_start_for_get_classes(
    execute_uc, user_repo, mock_client
):
    user_repo.get_user.return_value = _make_user()
    class_start = datetime(2027, 6, 10, 10, 0)
    goal = BookingGoal(class_start=class_start, class_name="WOD")
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 6, 10, 10, 0),
            spots_available=1,
            max_spots=10,
        )
    ]

    execute_uc.execute(123, goal)

    mock_client.get_classes.assert_called_once_with(class_start)


def test_execute_booking_creates_client_with_user_credentials(
    execute_uc, user_repo, factory, mock_client
):
    goal = _make_goal()

    user_repo.get_user.return_value = _make_user(
        email="test@gym.com", password="secret123"
    )
    mock_client.get_classes.return_value = [
        GymClass(
            name="WOD",
            class_start=datetime(2027, 3, 15, 18, 30),
            spots_available=1,
            max_spots=10,
        )
    ]

    execute_uc.execute(123, goal)

    factory.create.assert_called_once_with(
        _make_user(email="test@gym.com", password="secret123")
    )
