from datetime import datetime
from http import HTTPStatus

from bs4 import BeautifulSoup
from requests import Session

from constants import LOGIN_ENDPOINT, ERROR_TAG_ID, book_endpoint, classes_endpoint
from domain.exceptions import (
    BookingFailed,
    IncorrectCredentials,
    TooManyWrongAttempts,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
)
from domain.models import GymClass
from domain.ports.gym_client import IGymClient


class AimHarderClient(IGymClient):
    def __init__(self, email: str, password: str, box_id: int, box_name: str) -> None:
        self._session = self._login(email, password)
        self._box_id = box_id
        self._box_name = box_name

    @staticmethod
    def _login(email: str, password: str) -> Session:
        session = Session()
        response = session.post(
            LOGIN_ENDPOINT,
            data={"login": "Log in", "mail": email, "pw": password},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser").find(id=ERROR_TAG_ID)
        if soup is not None:
            if TooManyWrongAttempts.key_phrase in soup.text:
                raise TooManyWrongAttempts
            elif IncorrectCredentials.key_phrase in soup.text:
                raise IncorrectCredentials
        return session

    @staticmethod
    def _normalize_timeid(timeid: str) -> str:
        """Convert '1100_60' → '11:00', '0830_60' → '08:30'."""
        raw = timeid.split("_")[0]  # e.g. '1100'
        raw = raw.zfill(4)          # ensure 4 digits
        return f"{raw[:2]}:{raw[2:]}"

    def get_classes(self, target_day: datetime) -> list[GymClass]:
        response = self._session.get(
            classes_endpoint(self._box_name),
            params={"box": self._box_id, "day": target_day.strftime("%Y%m%d")},
        )
        bookings = response.json().get("bookings") or []
        return [
            GymClass(
                id=str(b["id"]),
                name=b["className"],
                time=self._normalize_timeid(b["timeid"]),
                spots_available=b["plazasDisp"],
                max_spots=b["plazas"],
            )
            for b in bookings
        ]

    def book_class(self, target_day: datetime, class_id: str) -> None:
        response = self._session.post(
            book_endpoint(self._box_name),
            data={"id": class_id, "day": target_day.strftime("%Y%m%d"), "insist": 0},
        )
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            if "bookState" in data and data["bookState"] == -2:
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if "errorMssg" not in data and "errorMssgLang" not in data:
                return
        raise BookingFailed(MESSAGE_BOOKING_FAILED_UNKNOWN)
