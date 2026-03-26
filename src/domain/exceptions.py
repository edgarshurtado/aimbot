MESSAGE_BOOKING_FAILED_NO_CREDIT = "No credit available"
MESSAGE_BOOKING_FAILED_UNKNOWN = "Unknown error"
MESSAGE_BOX_IS_CLOSED = "Box is closed"
MESSAGE_GYM_CLASS_NOT_FOUND = "Gym class not found"


class ErrorResponse(Exception):
    pass


class IncorrectCredentials(ErrorResponse):
    key_phrase = "Wrong email and/or password"


class BookingFailed(Exception):
    pass



class BoxClosed(Exception):
    pass
