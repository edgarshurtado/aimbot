import pytest
from datetime import datetime

from domain.exceptions import NoBookingGoal, BoxClosed
from domain.models import BookingGoal, GymClass, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_client import IGymClient, IGymClientFactory
from domain.ports.notifier import IGroupNotifier, IUserNotifier
from domain.ports.user_repository import IUserRepository
from application.use_cases.execute_booking import ExecuteBookingUseCase


@pytest.fixture
def execute_booking(mocker):
    user_repo = mocker.Mock(spec=IUserRepository)
    booking_repo = mocker.Mock(spec=IBookingRepository)
    factory = mocker.Mock(spec=IGymClientFactory)
    user_notifier = mocker.Mock(spec=IUserNotifier)
    group_notifier = mocker.Mock(spec=IGroupNotifier)
    mock_client = mocker.Mock(spec=IGymClient)
    factory.create.return_value = mock_client
    uc = ExecuteBookingUseCase(user_repo, booking_repo, factory, user_notifier, group_notifier)
    return uc, user_repo, booking_repo, factory, mock_client, user_notifier, group_notifier


def _make_user(user_id=123, email="a@b.com", password="pw"):
    return User(id=user_id, email=email, password=password)


def _make_goal():
    return BookingGoal(booking_date=datetime(2027, 3, 15, 18, 30), name="WOD")


def test_execute_booking_happy_path(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    client.get_classes.return_value = [GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=5, max_spots=20)]
    booking_repo.find_booking_goal.return_value = _make_goal()

    uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")

    client.book_class.assert_called_once_with(GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=5, max_spots=20))
    booking_repo.remove_booking_goal.assert_called_once_with(123, datetime(2027, 3, 15, 18, 30), "WOD")
    user_notifier.notify_user.assert_called_once()
    args = user_notifier.notify_user.call_args.args
    assert args[0] == 123
    assert "WOD" in args[1]
    group_notifier.notify_group.assert_called_once()


def test_execute_booking_matches_by_time_and_name(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    client.get_classes.return_value = [
        GymClass(name="OPEN", scheduled_at=datetime(2027, 3, 15, 10, 0), spots_available=1, max_spots=10),
        GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=1, max_spots=10),
        GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 10, 0), spots_available=1, max_spots=10),
    ]
    booking_repo.find_booking_goal.return_value = None

    uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")

    client.book_class.assert_called_once_with(GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=1, max_spots=10))


def test_execute_booking_user_not_found(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = None

    with pytest.raises(Exception):
        uc.execute(999, datetime(2027, 3, 15, 18, 30), "WOD")

    factory.create.assert_not_called()


def test_execute_booking_no_matching_class_raises(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    client.get_classes.return_value = [GymClass(name="OPEN", scheduled_at=datetime(2027, 3, 15, 10, 0), spots_available=1, max_spots=10)]

    with pytest.raises(NoBookingGoal):
        uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")


def test_execute_booking_box_closed(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    client.get_classes.return_value = []

    with pytest.raises(BoxClosed):
        uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")


def test_execute_booking_cleans_up_goal(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    client.get_classes.return_value = [GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=5, max_spots=20)]
    booking_repo.find_booking_goal.return_value = _make_goal()

    uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")

    booking_repo.remove_booking_goal.assert_called_once_with(123, datetime(2027, 3, 15, 18, 30), "WOD")


def test_execute_booking_no_goal_to_clean_up(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    client.get_classes.return_value = [GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=5, max_spots=20)]
    booking_repo.find_booking_goal.return_value = None

    uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")

    booking_repo.remove_booking_goal.assert_not_called()
    client.book_class.assert_called_once()


def test_execute_booking_notifies_user_and_group(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user(user_id=123)
    client.get_classes.return_value = [GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=5, max_spots=20)]
    booking_repo.find_booking_goal.return_value = None

    uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")

    user_notifier.notify_user.assert_called_once()
    group_notifier.notify_group.assert_called_once()
    msg = user_notifier.notify_user.call_args.args[1]
    assert "WOD" in msg


def test_execute_booking_uses_booking_date_for_get_classes(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user()
    booking_date = datetime(2027, 6, 10, 10, 0)
    client.get_classes.return_value = [GymClass(name="WOD", scheduled_at=datetime(2027, 6, 10, 10, 0), spots_available=1, max_spots=10)]
    booking_repo.find_booking_goal.return_value = None

    uc.execute(123, booking_date, "WOD")

    client.get_classes.assert_called_once_with(booking_date)


def test_execute_booking_creates_client_with_user_credentials(execute_booking):
    uc, user_repo, booking_repo, factory, client, user_notifier, group_notifier = execute_booking

    user_repo.get_user.return_value = _make_user(email="test@gym.com", password="secret123")
    client.get_classes.return_value = [GymClass(name="WOD", scheduled_at=datetime(2027, 3, 15, 18, 30), spots_available=1, max_spots=10)]
    booking_repo.find_booking_goal.return_value = None

    uc.execute(123, datetime(2027, 3, 15, 18, 30), "WOD")

    factory.create.assert_called_once_with("test@gym.com", "secret123")
