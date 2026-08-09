import random
import string
from datetime import datetime
from http import HTTPStatus

from requests import Session

from constants import (
    AUTH_COOKIE_DOMAIN,
    AUTH_COOKIE_NAME,
    LOGIN_ENDPOINT,
    book_endpoint,
    classes_endpoint,
)
from domain.exceptions import (
    AuthenticationFailed,
    BookingFailed,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
    MESSAGE_LOGIN_NOT_AUTHENTICATED,
    MESSAGE_LOGIN_REJECTED,
    MESSAGE_SESSION_EXPIRED,
)
from domain.models import GymClass
from domain.ports.gym_client import IGymClient
from infrastructure.aimharder.raw_booking import RawBooking

FINGERPRINT_LENGTH = 50


def _generate_fingerprint() -> str:
    """A per-login device identifier the platform expects alongside the credentials."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=FINGERPRINT_LENGTH))


def _raise_if_logged_out(data: dict) -> None:
    """Reject aimharder's logout sentinel.

    A request made without a valid session is answered with HTTP 200 and
    ``{"logout": 1}`` rather than an error status or an error message. It carries
    none of the keys the booking parser inspects, so left unchecked it reads as a
    successful booking.
    """
    if isinstance(data, dict) and data.get("logout"):
        raise AuthenticationFailed(MESSAGE_SESSION_EXPIRED)


def _platform_error(response) -> str:
    """Best-effort extraction of the platform's error message for diagnostics."""
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}"


def _rescope_auth_cookie(session: Session) -> None:
    """Pin the auth cookie to the parent domain.

    Login is served from login.aimharder.com while classes and bookings live on
    <box>.aimharder.com. A cookie returned without a domain attribute is host-only
    and would never reach the gym subdomain, so it is re-issued against the parent
    domain. Existing entries are cleared first: the jar normalises an explicit
    ``domain=aimharder.com`` to ``.aimharder.com``, which would otherwise leave two
    cookies of the same name and make later reads ambiguous.
    """
    existing = [c for c in session.cookies if c.name == AUTH_COOKIE_NAME]
    if not existing:
        return
    token = existing[0].value
    for cookie in existing:
        session.cookies.clear(cookie.domain, cookie.path, cookie.name)
    session.cookies.set(AUTH_COOKIE_NAME, token, domain=AUTH_COOKIE_DOMAIN, path="/")


class AimHarderClient(IGymClient):
    def __init__(self, email: str, password: str, box_id: int, box_name: str) -> None:
        self._session = self._login(email, password)
        self._box_id = box_id
        self._box_name = box_name
        self._id_map: dict[tuple[str, datetime], str] = {}

    @staticmethod
    def _login(email: str, password: str) -> Session:
        session = Session()
        response = session.post(
            LOGIN_ENDPOINT,
            json={
                "username": email,
                "password": password,
                "fingerprint": _generate_fingerprint(),
            },
        )
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise AuthenticationFailed(
                f"{MESSAGE_LOGIN_REJECTED}: {_platform_error(response)}"
            )
        response.raise_for_status()

        _rescope_auth_cookie(session)

        # Assert authentication positively. The platform answers an unauthenticated
        # session with ordinary-looking 200s rather than errors, so the presence of
        # the session cookie is the only trustworthy proof that login worked.
        if session.cookies.get(AUTH_COOKIE_NAME) is None:
            raise AuthenticationFailed(MESSAGE_LOGIN_NOT_AUTHENTICATED)
        return session

    def get_classes(self, target_day: datetime) -> list[GymClass]:
        response = self._session.get(
            classes_endpoint(self._box_name),
            params={"box": self._box_id, "day": target_day.strftime("%Y%m%d")},
        )
        data = response.json()
        _raise_if_logged_out(data)
        bookings = data.get("bookings") or []
        gym_classes = []
        for b in bookings:
            raw = RawBooking.from_dict(b)
            gym_class = raw.to_gym_class(target_day.date())
            self._id_map[(gym_class.name, gym_class.class_start)] = raw.id
            gym_classes.append(gym_class)
        return gym_classes

    def book_class(self, gym_class: GymClass) -> None:
        class_id = self._id_map[(gym_class.name, gym_class.class_start)]
        response = self._session.post(
            book_endpoint(self._box_name),
            data={
                "id": class_id,
                "day": gym_class.class_start.strftime("%Y%m%d"),
                "insist": 0,
            },
        )
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            _raise_if_logged_out(data)
            if "bookState" in data and data["bookState"] == -2:
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if "errorMssg" not in data and "errorMssgLang" not in data:
                return
        raise BookingFailed(MESSAGE_BOOKING_FAILED_UNKNOWN)
