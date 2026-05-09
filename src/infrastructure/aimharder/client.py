from datetime import datetime
from http import HTTPStatus

from bs4 import BeautifulSoup
from requests import Session

from constants import LOGIN_ENDPOINT, ERROR_TAG_ID, book_endpoint, classes_endpoint
from domain.exceptions import (
    AuthenticationFailed,
    BookingFailed,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
)
from domain.models import GymClass
from domain.ports.gym_client import IGymClient
from infrastructure.aimharder.exceptions import (
    IncorrectCredentials,
    TooManyWrongAttempts,
)
from infrastructure.aimharder.raw_booking import RawBooking


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
            data={"login": "Log in", "mail": email, "pw": password},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser").find(id=ERROR_TAG_ID)
        if soup is not None and soup.text:
            if IncorrectCredentials.key_phrase in soup.text:
                raise AuthenticationFailed(soup.text)
            if TooManyWrongAttempts.key_phrase in soup.text:
                raise AuthenticationFailed(soup.text)
            raise AuthenticationFailed(soup.text)
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
            data={"id": class_id, "day": gym_class.class_start.strftime("%Y%m%d"), "insist": 0},
        )
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            if "bookState" in data and data["bookState"] == -2:
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if "errorMssg" not in data and "errorMssgLang" not in data:
                return
        raise BookingFailed(MESSAGE_BOOKING_FAILED_UNKNOWN)
