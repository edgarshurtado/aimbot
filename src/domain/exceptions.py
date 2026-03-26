MESSAGE_BOOKING_FAILED_NO_CREDIT = "No credit available"
MESSAGE_BOOKING_FAILED_UNKNOWN = "Unknown error"
MESSAGE_BOX_IS_CLOSED = "Box is closed"
MESSAGE_GYM_CLASS_NOT_FOUND = "Gym class not found"


class BookingFailed(Exception):
    """Any failure to complete a booking: class not found, box closed, no credit, platform error."""

    pass


class AuthenticationFailed(Exception):
    """User credentials were rejected by the platform."""

    pass


class UserNotFound(Exception):
    """Requested user does not exist in the repository."""

    pass
