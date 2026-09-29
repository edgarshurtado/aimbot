MESSAGE_BOOKING_FAILED_NO_CREDIT = "No credit available"
MESSAGE_BOOKING_FAILED_UNKNOWN = "The gym rejected the booking without saying why"
MESSAGE_LOGIN_REJECTED = "Credentials rejected by the platform"
MESSAGE_LOGIN_NOT_AUTHENTICATED = (
    "Login returned no session cookie — credentials were not accepted"
)
MESSAGE_SESSION_EXPIRED = "Session is no longer authenticated — nothing was booked"
MESSAGE_TIMETABLE_EMPTY = "The gym hasn't published a timetable for that day"
MESSAGE_GYM_CLASS_NOT_FOUND = "Gym class not found"


class BookingFailed(Exception):
    """Any failure to complete a booking: class not found, empty timetable, no credit, platform error."""

    pass


class AuthenticationFailed(Exception):
    """User credentials were rejected by the platform."""

    pass


class UserNotFound(Exception):
    """Requested user does not exist in the repository."""

    pass
