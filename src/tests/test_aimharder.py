import json

import pytest
import responses as rsps_lib
from datetime import date, datetime
from http import HTTPStatus
from unittest.mock import ANY

from requests import Session

from constants import LOGIN_ENDPOINT, book_endpoint, classes_endpoint
from domain.models import GymClass
from domain.exceptions import AuthenticationFailed, BookingFailed
from domain.ports.gym_client import IGymClientFactory
from infrastructure.aimharder.client import REQUEST_TIMEOUT_SECONDS, AimHarderClient
from infrastructure.aimharder.client_factory import AimHarderClientFactory
from infrastructure.aimharder.gym_config import IAimHarderGym
from infrastructure.aimharder.raw_booking import RawBooking

BOX_NAME = "themonkeybox"
BOX_ID = 9824
DAYS_IN_ADVANCE = 3
AUTH_TOKEN = "session-token-abc123"

# A realistic Set-Cookie: the expires date contains a comma, which is exactly what
# breaks naive parsing of requests' comma-joined duplicate headers.
AUTH_COOKIE_HEADER = (
    f"amhrdrauth={AUTH_TOKEN}; expires=Wed, 01 Jan 2028 00:00:00 GMT;"
    " domain=aimharder.com; path=/; secure; HttpOnly"
)


def _mock_login_success(http_mock):
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        json={"user": {"id": 1}},
        headers={"Set-Cookie": AUTH_COOKIE_HEADER},
    )


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


def test_login_posts_json_credentials(http_mock):
    """The platform rejects form-encoded bodies with LOGIN_ERROR_MALFORMED_BODY."""
    _mock_login_success(http_mock)
    AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    request = http_mock.calls[0].request
    assert request.url == LOGIN_ENDPOINT
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.body) == {
        "username": "foo@bar.com",
        "password": "pass",
        "fingerprint": ANY,
    }


def test_login_installs_auth_cookie_on_session(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    assert client._session.cookies.get("amhrdrauth") == AUTH_TOKEN


def test_login_widens_a_host_only_auth_cookie_to_the_gym_subdomain(http_mock):
    """Login happens on login.aimharder.com but every later call goes to
    <box>.aimharder.com. A cookie returned without a domain attribute is host-only
    and would never be sent to the gym subdomain, so it has to be re-scoped."""
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        json={"user": {"id": 1}},
        headers={"Set-Cookie": f"amhrdrauth={AUTH_TOKEN}; path=/; secure; HttpOnly"},
    )
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={"bookings": []})
    client.get_classes(datetime(2027, 3, 15))

    assert f"amhrdrauth={AUTH_TOKEN}" in http_mock.calls[-1].request.headers.get(
        "Cookie", ""
    )


def test_login_sends_a_fresh_fingerprint_each_time(http_mock):
    _mock_login_success(http_mock)
    _mock_login_success(http_mock)

    AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    first = json.loads(http_mock.calls[0].request.body)["fingerprint"]
    second = json.loads(http_mock.calls[1].request.body)["fingerprint"]
    assert first != second
    assert len(first) == 50


def test_login_finds_auth_cookie_set_on_a_redirect_hop(http_mock):
    """The cookie may arrive on an intermediate response rather than the final one."""
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        status=302,
        headers={
            "Set-Cookie": AUTH_COOKIE_HEADER,
            "Location": "https://login.aimharder.com/api/session",
        },
    )
    http_mock.add(
        rsps_lib.GET,
        "https://login.aimharder.com/api/session",
        json={"user": {"id": 1}},
    )

    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    assert client._session.cookies.get("amhrdrauth") == AUTH_TOKEN


# ── Login failure detection ───────────────────────────────────────────────────


def test_login_rejects_wrong_credentials(http_mock):
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        status=401,
        json={"error": {"code": 401, "message": "LOGIN_ERROR_LOGIN"}},
    )
    with pytest.raises(AuthenticationFailed):
        AimHarderClient("foo@bar.com", "wrongpass", BOX_ID, BOX_NAME)


def test_login_surfaces_the_platform_error_message(http_mock):
    http_mock.add(
        rsps_lib.POST,
        LOGIN_ENDPOINT,
        status=401,
        json={"error": {"code": 401, "message": "LOGIN_ERROR_LOGIN"}},
    )
    with pytest.raises(AuthenticationFailed, match="LOGIN_ERROR_LOGIN"):
        AimHarderClient("foo@bar.com", "wrongpass", BOX_ID, BOX_NAME)


def test_login_fails_when_no_auth_cookie_is_issued(http_mock):
    """Regression guard for the silent-booking bug.

    A 200 that carries no auth cookie means we are not logged in. Returning that
    session made every later call run unauthenticated: the class listing still
    answered with real data, and the booking call reported success while booking
    nothing. Login must never hand back a session it cannot vouch for.
    """
    http_mock.add(rsps_lib.POST, LOGIN_ENDPOINT, status=200, json={"user": {"id": 1}})

    with pytest.raises(AuthenticationFailed):
        AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)


def test_login_raises_on_server_error(http_mock):
    http_mock.add(rsps_lib.POST, LOGIN_ENDPOINT, status=500)
    with pytest.raises(Exception):
        AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)


# ── get_classes tests ─────────────────────────────────────────────────────────


def test_get_classes_returns_gym_class_objects(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(
        rsps_lib.GET,
        classes_endpoint(BOX_NAME),
        json={
            "bookings": [
                {
                    "id": "42",
                    "timeid": "1100_60",
                    "className": "WOD",
                    "ocupation": 15,
                    "limit": 20,
                }
            ]
        },
    )

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

    http_mock.add(
        rsps_lib.GET,
        classes_endpoint(BOX_NAME),
        json={
            "bookings": [
                {
                    "id": "1",
                    "timeid": "0830_60",
                    "className": "OPEN",
                    "ocupation": 12,
                    "limit": 15,
                }
            ]
        },
    )

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].class_start == datetime(2027, 3, 15, 8, 30)


# ── book_class tests ──────────────────────────────────────────────────────────


def test_book_class_success(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(
        name="WOD",
        class_start=datetime(2027, 3, 2, 11, 0),
        spots_available=5,
        max_spots=20,
    )
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(rsps_lib.POST, book_endpoint(BOX_NAME), json={}, status=200)

    result = client.book_class(gym_class)
    assert result is None


def test_book_class_no_credit(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(
        name="WOD",
        class_start=datetime(2027, 3, 2, 11, 0),
        spots_available=5,
        max_spots=20,
    )
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(
        rsps_lib.POST, book_endpoint(BOX_NAME), json={"bookState": -2}, status=200
    )

    with pytest.raises(BookingFailed):
        client.book_class(gym_class)


def test_book_class_error_response(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(
        name="WOD",
        class_start=datetime(2027, 3, 2, 11, 0),
        spots_available=5,
        max_spots=20,
    )
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(
        rsps_lib.POST,
        book_endpoint(BOX_NAME),
        json={"errorMssg": "some error"},
        status=200,
    )

    with pytest.raises(BookingFailed):
        client.book_class(gym_class)


def test_book_class_server_error(http_mock):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(
        name="WOD",
        class_start=datetime(2027, 3, 2, 11, 0),
        spots_available=5,
        max_spots=20,
    )
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(rsps_lib.POST, book_endpoint(BOX_NAME), status=500)

    with pytest.raises(BookingFailed):
        client.book_class(gym_class)


# ── Logout sentinel ───────────────────────────────────────────────────────────


def test_book_class_rejects_logout_sentinel(http_mock):
    """Regression guard for the silent-booking bug.

    aimharder answers a booking attempt from an unauthenticated session with
    HTTP 200 and {"logout": 1}. That body carries none of the error keys the
    client looked for, so it was read as a successful booking and the member was
    told their class was booked when nothing had been reserved.
    """
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(
        name="WOD",
        class_start=datetime(2027, 3, 2, 11, 0),
        spots_available=5,
        max_spots=20,
    )
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    http_mock.add(
        rsps_lib.POST, book_endpoint(BOX_NAME), json={"logout": 1}, status=200
    )

    with pytest.raises(AuthenticationFailed):
        client.book_class(gym_class)


def test_get_classes_rejects_logout_sentinel(http_mock):
    """Same sentinel one layer earlier — must not read as 'the box is closed'."""
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(rsps_lib.GET, classes_endpoint(BOX_NAME), json={"logout": 1})

    with pytest.raises(AuthenticationFailed):
        client.get_classes(datetime(2027, 3, 15))


# ── Adversarial edge cases ────────────────────────────────────────────────────


def test_get_classes_normalizes_3digit_timeid(http_mock):
    """'900_60' → '09:00' (3-digit hour must be zero-padded)."""
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(
        rsps_lib.GET,
        classes_endpoint(BOX_NAME),
        json={
            "bookings": [
                {
                    "id": "1",
                    "timeid": "900_60",
                    "className": "WOD",
                    "ocupation": 8,
                    "limit": 10,
                }
            ]
        },
    )

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].class_start == datetime(2027, 3, 15, 9, 0)


def test_get_classes_missing_plazas_defaults_to_zero(http_mock):
    """Missing ocupation/limit should not crash — default to 0."""
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    http_mock.add(
        rsps_lib.GET,
        classes_endpoint(BOX_NAME),
        json={"bookings": [{"id": "5", "timeid": "1200_60", "className": "WOD"}]},
    )

    result = client.get_classes(datetime(2027, 3, 15))
    assert result[0].max_spots == 0
    assert result[0].spots_available == 0


# ── Request timeouts ──────────────────────────────────────────────────────────
#
# requests waits indefinitely when no timeout is given, and a hang is the one
# failure "catch everything" cannot catch — the caller's thread simply never
# returns. Asserted here rather than in an integration test because `responses`
# does not expose the timeout kwarg.


def test_login_request_carries_a_timeout(mocker):
    post = mocker.patch.object(Session, "post")
    post.return_value.status_code = HTTPStatus.OK

    # No auth cookie is issued through the patched call, so login rejects the
    # session — irrelevant here; the request has already been made.
    with pytest.raises(AuthenticationFailed):
        AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    assert post.call_args.kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS


def test_class_listing_request_carries_a_timeout(http_mock, mocker):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)

    get = mocker.patch.object(client._session, "get")
    get.return_value.json.return_value = {"bookings": []}

    client.get_classes(datetime(2027, 3, 15))

    assert get.call_args.kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS


def test_booking_request_carries_a_timeout(http_mock, mocker):
    _mock_login_success(http_mock)
    client = AimHarderClient("foo@bar.com", "pass", BOX_ID, BOX_NAME)
    gym_class = GymClass(
        name="WOD",
        class_start=datetime(2027, 3, 2, 11, 0),
        spots_available=5,
        max_spots=20,
    )
    client._id_map[("WOD", datetime(2027, 3, 2, 11, 0))] = "42"

    post = mocker.patch.object(client._session, "post")
    post.return_value.status_code = HTTPStatus.OK
    post.return_value.json.return_value = {}

    client.book_class(gym_class)

    assert post.call_args.kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS


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
    result = IAimHarderGym.booking_trigger_time(
        gym, class_start=datetime(2027, 3, 15, 18, 30)
    )
    assert result == datetime(2027, 3, 12, 18, 30)


# ── RawBooking tests ──────────────────────────────────────────────────────────


def test_raw_booking_from_dict():
    raw = RawBooking.from_dict(
        {
            "id": 42,
            "className": "WOD",
            "timeid": "1100_60",
            "limit": 20,
            "ocupation": 15,
        }
    )
    assert raw.id == "42"
    assert raw.class_name == "WOD"
    assert raw.timeid == "1100_60"
    assert raw.limit == 20
    assert raw.ocupation == 15


def test_raw_booking_spots_available():
    raw = RawBooking.from_dict(
        {
            "id": "1",
            "className": "WOD",
            "timeid": "1100_60",
            "limit": 20,
            "ocupation": 15,
        }
    )
    assert raw.spots_available == 5


def test_raw_booking_missing_fields_default_to_zero():
    raw = RawBooking.from_dict({"id": "1", "className": "WOD", "timeid": "1100_60"})
    assert raw.limit == 0
    assert raw.ocupation == 0
    assert raw.spots_available == 0


def test_raw_booking_to_gym_class():
    raw = RawBooking.from_dict(
        {
            "id": "42",
            "className": "WOD",
            "timeid": "1100_60",
            "limit": 20,
            "ocupation": 15,
        }
    )
    gym_class = raw.to_gym_class(date(2027, 3, 15))
    assert isinstance(gym_class, GymClass)
    assert gym_class.name == "WOD"
    assert gym_class.class_start == datetime(2027, 3, 15, 11, 0)
    assert gym_class.max_spots == 20
    assert gym_class.spots_available == 5
