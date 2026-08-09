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
    BookingFailed,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
)
from domain.models import GymClass
from domain.ports.gym_client import IGymClient
from infrastructure.aimharder.raw_booking import RawBooking

FINGERPRINT_LENGTH = 50


def _generate_fingerprint() -> str:
    """A per-login device identifier the platform expects alongside the credentials."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=FINGERPRINT_LENGTH))


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
        response.raise_for_status()

        _rescope_auth_cookie(session)
        return session

    def get_classes(self, target_day: datetime) -> list[GymClass]:
        response = self._session.get(
            classes_endpoint(self._box_name),
            params={"box": self._box_id, "day": target_day.strftime("%Y%m%d")},
        )
        bookings = response.json().get("bookings") or []
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
            if "bookState" in data and data["bookState"] == -2:
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if "errorMssg" not in data and "errorMssgLang" not in data:
                return
        raise BookingFailed(MESSAGE_BOOKING_FAILED_UNKNOWN)
