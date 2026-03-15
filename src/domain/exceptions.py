MESSAGE_BOOKING_FAILED_NO_CREDIT = "No credit available"
MESSAGE_BOOKING_FAILED_UNKNOWN = "Unknown error"
MESSAGE_BOX_IS_CLOSED = "Box is closed"


class ErrorResponse(Exception):
    pass


class IncorrectCredentials(ErrorResponse):
    key_phrase = "Wrong email and/or password"


class BookingFailed(Exception):
    pass


class NoBookingGoal(Exception):
    pass


class BoxClosed(Exception):
    pass
