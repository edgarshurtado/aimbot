import pytest
import responses as rsps_lib
from datetime import date, datetime

from constants import LOGIN_ENDPOINT, book_endpoint, classes_endpoint
from domain.models import GymClass
from domain.exceptions import AuthenticationFailed, BookingFailed
from domain.ports.gym_client import IGymClientFactory
from infrastructure.aimharder.client import AimHarderClient
from infrastructure.aimharder.client_factory import AimHarderClientFactory
from infrastructure.aimharder.gym_config import IAimHarderGym
from infrastructure.aimharder.raw_booking import RawBooking


BOX_NAME = "themonkeybox"
BOX_ID = 9824
DAYS_IN_ADVANCE = 3
LOGIN_SUCCESS_BODY = b'<html><span id="loginErrors"></span></html>'


def _mock_login_success(http_mock):
    http_mock.add(rsps_lib.POST, LOGIN_ENDPOINT, body=LOGIN_SUCCESS_BODY)


@pytest.fixture
def gym(mocker):
    mock = mocker.Mock(spec=IAimHarderGym)
    mock.box_id = BOX_ID
    mock.box_name = BOX_NAME
    mock.days_in_advance = DAYS_IN_ADVANCE
    return mock


@pytest.fixture
def factory(gym):
    return AimHarderClientFactory(gym=gym)


# ── Login tests ───────────────────────────────────────────────────────────────

def test_client_login_incorrect_credentials(http_mock):
    http_mock.add(rsps_lib.POST, LOGIN_ENDPOINT, body=b'<html><span id="loginErrors">Wrong email and/or password</span></html>')
    with pytest.raises(AuthenticationFailed):
        AimHarderClient("foo@bar.com", "wrongpass", BOX_ID, BOX_NAME)


def test_client_login_unknown_error(http_mock):
    http_mock.add(rsps_lib.POST, LOGIN_ENDPOINT, body=b'<html><span id="loginErrors">some unexpected error</span></html>')
    with pytest.raises(AuthenticationFailed):
        AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)


# ── get_classes tests ─────────────────────────────────────────────────────────

def test_get_classes_returns_gym_class_objects(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={
        "bookings": [
            {"id": "42", "timeid": "1100_60", "className": "WOD", "ocupation": 15, "limit": 20}
        ]
    })

    result = client.get_classes(datetime(2027, 3, 15))
    assert isinstance(result, list)
    assert len(result) == 1
    gym_class = result[0]
    assert isinstance(gym_class, GymClass)
    assert gym_class.name == "WOD"
    assert gym_class.class_start == datetime(2027, 3, 15, 11, 0)
    assert gym_class.spots_available == 5
    assert gym_class.max_spots == 20


def test_get_classes_empty_bookings(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={"bookings": []})

    result = client.get_classes(datetime(2027, 3, 15))
    assert result == []


def test_get_classes_no_bookings_key(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={})

    result = client.get_classes(datetime(2027, 3, 15))
    assert result == []


def test_get_classes_normalizes_timeid_to_hhmm(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={
        "bookings": [
            {"id": "1", "timeid": "0830_60", "className": "OPEN", "ocupation": 12, "limit": 15}
        ]
    })

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].class_start == datetime(2027, 3, 15, 8, 30)


# ── book_class tests ──────────────────────────────────────────────────────────

def test_book_class_success(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(name="WOD", class_start=datetime(2027, 3, 2, 11, 0), spots_available=5, max_spots=20)
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(rsps_lib.POST, book_endpoint(BOX_NAME), json={}, status=200)

    result = client.book_class(gym_class)
    assert result is None


def test_book_class_no_credit(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(name="WOD", class_start=datetime(2027, 3, 2, 11, 0), spots_available=5, max_spots=20)
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(rsps_lib.POST, book_endpoint(BOX_NAME), json={"bookState": -2}, status=200)

    with pytest.raises(BookingFailed):
        client.book_class(gym_class)


def test_book_class_error_response(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(name="WOD", class_start=datetime(2027, 3, 2, 11, 0), spots_available=5, max_spots=20)
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(rsps_lib.POST, book_endpoint(BOX_NAME), json={"errorMssg": "some error"}, status=200)

    with pytest.raises(BookingFailed):
        client.book_class(gym_class)


def test_book_class_server_error(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(name="WOD", class_start=datetime(2027, 3, 2, 11, 0), spots_available=5, max_spots=20)
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(rsps_lib.POST, book_endpoint(BOX_NAME), status=500)

    with pytest.raises(BookingFailed):
        client.book_class(gym_class)


# ── Adversarial edge cases ────────────────────────────────────────────────────

def test_get_classes_normalizes_3digit_timeid(http_mock):
    """'900_60' → '09:00' (3-digit hour must be zero-padded)."""
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={
        "bookings": [
            {"id": "1", "timeid": "900_60", "className": "WOD", "ocupation": 8, "limit": 10}
        ]
    })

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].class_start == datetime(2027, 3, 15, 9, 0)


def test_get_classes_missing_plazas_defaults_to_zero(http_mock):
    """Missing ocupation/limit should not crash — default to 0."""
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={
        "bookings": [{"id": "5", "timeid": "1200_60", "className": "WOD"}]
    })

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].max_spots == 0
    assert result[0].spots_available == 0


# ── Factory tests ─────────────────────────────────────────────────────────────

def test_factory_create_returns_client(factory, http_mock):
    from domain.models import User
    _mock_login_success(http_mock)
    client = factory.create(User(id=1, email="foo@bar.com", password="pass"))
    assert isinstance(client, AimHarderClient)


def test_factory_implements_gym_client_factory_interface(factory):
    assert isinstance(factory, IGymClientFactory)


def test_aim_harder_gym_booking_trigger_time(gym):
    from datetime import timedelta
    gym.days_in_advance = 3
    result = IAimHarderGym.booking_trigger_time(gym, class_start=datetime(2027, 3, 15, 18, 30))
    assert result == datetime(2027, 3, 12, 18, 30)


# ── RawBooking tests ──────────────────────────────────────────────────────────

def test_raw_booking_from_dict():
    raw = RawBooking.from_dict({"id": 42, "className": "WOD", "timeid": "1100_60", "limit": 20, "ocupation": 15})
    assert raw.id == "42"
    assert raw.class_name == "WOD"
    assert raw.timeid == "1100_60"
    assert raw.limit == 20
    assert raw.ocupation == 15


def test_raw_booking_spots_available():
    raw = RawBooking.from_dict({"id": "1", "className": "WOD", "timeid": "1100_60", "limit": 20, "ocupation": 15})
    assert raw.spots_available == 5


def test_raw_booking_missing_fields_default_to_zero():
    raw = RawBooking.from_dict({"id": "1", "className": "WOD", "timeid": "1100_60"})
    assert raw.limit == 0
    assert raw.ocupation == 0
    assert raw.spots_available == 0


def test_raw_booking_to_gym_class():
    raw = RawBooking.from_dict({"id": "42", "className": "WOD", "timeid": "1100_60", "limit": 20, "ocupation": 15})
    gym_class = raw.to_gym_class(date(2027, 3, 15))
    assert isinstance(gym_class, GymClass)
    assert gym_class.name == "WOD"
    assert gym_class.class_start == datetime(2027, 3, 15, 11, 0)
    assert gym_class.max_spots == 20
    assert gym_class.spots_available == 5
