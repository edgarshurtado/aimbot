import pytest
from datetime import datetime

from domain.exceptions import UserNotFound
from domain.models import GymClass, User
from domain.ports.gym_client import IGymClient, IGymClientFactory
from application.use_cases.list_day_classes import ListDayClassesUseCase
from tests.fakes import InMemoryUserRepository


DEFAULT_USER = User(id=123, email="a@b.com", password="pw")
DAY = datetime(2027, 3, 15)


def _gym_class(name: str, hour: int, minute: int = 0) -> GymClass:
    return GymClass(
        name=name,
        class_start=datetime(2027, 3, 15, hour, minute),
        spots_available=5,
        max_spots=20,
    )


@pytest.fixture
def user_repo():
    return InMemoryUserRepository(users=[DEFAULT_USER])


@pytest.fixture
def mock_client(mocker):
    return mocker.Mock(spec=IGymClient)


@pytest.fixture
def factory(mocker, mock_client):
    f = mocker.Mock(spec=IGymClientFactory)
    f.create.return_value = mock_client
    return f


@pytest.fixture
def list_uc(user_repo, factory):
    return ListDayClassesUseCase(user_repo, factory)


def test_lists_the_timetable_for_the_requested_day(list_uc, mock_client):
    mock_client.get_classes.return_value = [_gym_class("WOD", 18, 30)]

    assert list_uc.execute(DEFAULT_USER.id, DAY) == [_gym_class("WOD", 18, 30)]
    mock_client.get_classes.assert_called_once_with(DAY)


def test_orders_classes_by_start_time_then_name(list_uc, mock_client):
    """The keyboard's order must be stable; the API's is not a documented guarantee."""
    mock_client.get_classes.return_value = [
        _gym_class("WOD", 18, 30),
        _gym_class("OPEN", 7, 30),
        _gym_class("GYMNASTIC", 18, 30),
    ]

    assert list_uc.execute(DEFAULT_USER.id, DAY) == [
        _gym_class("OPEN", 7, 30),
        _gym_class("GYMNASTIC", 18, 30),
        _gym_class("WOD", 18, 30),
    ]


def test_empty_timetable_lists_nothing(list_uc, mock_client):
    mock_client.get_classes.return_value = []

    assert list_uc.execute(DEFAULT_USER.id, DAY) == []


def test_builds_the_client_from_the_members_credentials(list_uc, factory, mock_client):
    mock_client.get_classes.return_value = []

    list_uc.execute(DEFAULT_USER.id, DAY)

    factory.create.assert_called_once_with(DEFAULT_USER)


def test_unknown_member_is_rejected_before_any_login(factory, mock_client):
    uc = ListDayClassesUseCase(InMemoryUserRepository(), factory)

    with pytest.raises(UserNotFound):
        uc.execute(999, DAY)

    factory.create.assert_not_called()
