import pytest
from datetime import datetime

from domain.models import GymClass
from domain.ports.gym_client import IGymClient, IGymClientFactory, IGymPlatformConfig
from domain.exceptions import TooManyWrongAttempts, IncorrectCredentials, BookingFailed
from infrastructure.aimharder.client import AimHarderClient
from infrastructure.aimharder.client_factory import AimHarderClientFactory


def _mock_login_success(mocker):
    """Patch requests.Session.post to return a successful login response."""
    mock_resp = mocker.Mock()
    mock_resp.content = b'<html><span id="loginErrors"></span></html>'
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.Session.post", return_value=mock_resp)
    return mock_resp


@pytest.fixture
def factory():
    return AimHarderClientFactory(box_id=9824, box_name="themonkeybox")


# ── Login tests ───────────────────────────────────────────────────────────────

def test_client_login_success(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")
    assert client is not None


def test_client_login_too_many_attempts(mocker):
    mock_resp = mocker.Mock()
    mock_resp.content = b'<html><span id="loginErrors">demasiadas veces</span></html>'
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.Session.post", return_value=mock_resp)

    with pytest.raises(TooManyWrongAttempts):
        AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")


def test_client_login_incorrect_credentials(mocker):
    mock_resp = mocker.Mock()
    mock_resp.content = b'<html><span id="loginErrors">incorrecto</span></html>'
    mock_resp.raise_for_status = mocker.Mock()
    mocker.patch("requests.Session.post", return_value=mock_resp)

    with pytest.raises(IncorrectCredentials):
        AimHarderClient("foo@bar.com", "wrongpass", 9824, "themonkeybox")


# ── get_classes tests ─────────────────────────────────────────────────────────

def test_get_classes_returns_gym_class_objects(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    get_resp = mocker.Mock()
    get_resp.json.return_value = {
        "bookings": [
            {"id": "42", "timeid": "1100_60", "className": "WOD", "plazasDisp": 5, "plazas": 20}
        ]
    }
    mocker.patch("requests.Session.get", return_value=get_resp)

    result = client.get_classes(datetime(2027, 3, 15))
    assert isinstance(result, list)
    assert len(result) == 1
    gym_class = result[0]
    assert isinstance(gym_class, GymClass)
    assert gym_class.id == "42"
    assert gym_class.name == "WOD"
    assert gym_class.time == "11:00"
    assert gym_class.spots_available == 5
    assert gym_class.max_spots == 20


def test_get_classes_empty_bookings(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    get_resp = mocker.Mock()
    get_resp.json.return_value = {"bookings": []}
    mocker.patch("requests.Session.get", return_value=get_resp)

    result = client.get_classes(datetime(2027, 3, 15))
    assert result == []


def test_get_classes_no_bookings_key(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    get_resp = mocker.Mock()
    get_resp.json.return_value = {}
    mocker.patch("requests.Session.get", return_value=get_resp)

    result = client.get_classes(datetime(2027, 3, 15))
    assert result == []


def test_get_classes_normalizes_timeid_to_hhmm(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    get_resp = mocker.Mock()
    get_resp.json.return_value = {
        "bookings": [
            {"id": "1", "timeid": "0830_60", "className": "OPEN", "plazasDisp": 3, "plazas": 15}
        ]
    }
    mocker.patch("requests.Session.get", return_value=get_resp)

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].time == "08:30"


# ── book_class tests ──────────────────────────────────────────────────────────

def test_book_class_success(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    post_resp = mocker.Mock()
    post_resp.status_code = 200
    post_resp.json.return_value = {}
    mocker.patch("requests.Session.post", return_value=post_resp)

    result = client.book_class(datetime(2027, 3, 2), "42")
    assert result is None


def test_book_class_no_credit(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    post_resp = mocker.Mock()
    post_resp.status_code = 200
    post_resp.json.return_value = {"bookState": -2}
    mocker.patch("requests.Session.post", return_value=post_resp)

    with pytest.raises(BookingFailed):
        client.book_class(datetime(2027, 3, 2), "42")


def test_book_class_error_response(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    post_resp = mocker.Mock()
    post_resp.status_code = 200
    post_resp.json.return_value = {"errorMssg": "some error"}
    mocker.patch("requests.Session.post", return_value=post_resp)

    with pytest.raises(BookingFailed):
        client.book_class(datetime(2027, 3, 2), "42")


def test_book_class_server_error(mocker):
    _mock_login_success(mocker)
    client = AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")

    post_resp = mocker.Mock()
    post_resp.status_code = 500
    mocker.patch("requests.Session.post", return_value=post_resp)

    with pytest.raises(BookingFailed):
        client.book_class(datetime(2027, 3, 2), "42")


# ── Factory tests ─────────────────────────────────────────────────────────────

def test_factory_create_returns_client(factory, mocker):
    _mock_login_success(mocker)
    client = factory.create("foo@bar.com", "pass")
    assert isinstance(client, AimHarderClient)


def test_factory_booking_trigger_time(factory):
    result = factory.booking_trigger_time(datetime(2027, 3, 15, 18, 30))
    assert result == datetime(2027, 3, 12, 18, 30)


def test_factory_implements_both_interfaces(factory):
    assert isinstance(factory, IGymClientFactory)
    assert isinstance(factory, IGymPlatformConfig)
