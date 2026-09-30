from datetime import datetime

from domain.exceptions import (
    AuthenticationFailed,
    BookingFailed,
    MESSAGE_GYM_CLASS_NOT_FOUND,
    UserNotFound,
)
from domain.models import BookingGoal, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_client import IGymClientFactory
from domain.ports.notifier import IUserNotifier
from domain.ports.user_repository import IUserRepository

MEMBER_MESSAGE_SIGN_IN = "AimBot couldn't sign in to your gym account."
MEMBER_MESSAGE_UNKNOWN = "Something went wrong on our side."


class ExecuteBookingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        booking_repo: IBookingRepository,
        gym_client_factory: IGymClientFactory,
        user_notifier: IUserNotifier,
    ) -> None:
        self._user_repo = user_repo
        self._booking_repo = booking_repo
        self._gym_client_factory = gym_client_factory
        self._user_notifier = user_notifier

    def execute(self, user_id: int, booking_goal: BookingGoal) -> None:
        if booking_goal.class_start < datetime.now():
            # A Lapsed Booking Goal is residue, not intent: nothing failed now,
            # so it is swept without an attempt and without a message.
            self._booking_repo.remove_booking_goal(user_id, booking_goal)
            return

        try:
            user = self._attempt(user_id, booking_goal)
        except Exception as exc:
            # One attempt per goal: it is consumed whatever the outcome
            # (ADR-0001). Re-raised so the scheduler still logs the traceback.
            self._booking_repo.remove_booking_goal(user_id, booking_goal)
            self._user_notifier.notify_user(
                user_id, _failure_message(booking_goal, _member_reason(exc))
            )
            raise

        # Outside the try: once the class is booked, a failure to record or
        # confirm it must never reach the member as a failed booking.
        self._booking_repo.remove_booking_goal(user_id, booking_goal)
        msg = (
            f"class booked for {user.email}: {booking_goal.class_name} "
            f"{booking_goal.class_start.strftime('%H:%M')}"
        )
        self._user_notifier.notify_user(user_id, msg)

    def _attempt(self, user_id: int, booking_goal: BookingGoal) -> User:
        """Book the goal's class, or raise. Returns the member it was booked for."""
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise UserNotFound(f"User {user_id} not found")

        client = self._gym_client_factory.create(user)
        classes = client.get_classes(booking_goal.class_start)

        matched = next(
            (
                c
                for c in classes
                if c.class_start == booking_goal.class_start
                and c.name == booking_goal.class_name
            ),
            None,
        )
        if matched is None:
            # The member's message header already names the class and its time.
            raise BookingFailed(MESSAGE_GYM_CLASS_NOT_FOUND)

        client.book_class(matched)
        return user


def _member_reason(exc: Exception) -> str:
    if isinstance(exc, BookingFailed):
        return str(exc)
    if isinstance(exc, AuthenticationFailed):
        return MEMBER_MESSAGE_SIGN_IN
    return MEMBER_MESSAGE_UNKNOWN


def _failure_message(booking_goal: BookingGoal, reason: str) -> str:
    return (
        f"❌ Couldn't book {booking_goal.class_name}\n"
        f"📅 {booking_goal.class_start.strftime('%d/%m/%Y %H:%M')}\n"
        f"{reason}"
    )
