class AimHarderErrorResponse(Exception):
    """Base for errors parsed from AimHarder HTML responses."""

    key_phrase: str | None = None


class IncorrectCredentials(AimHarderErrorResponse):
    key_phrase = "incorrecto"


class TooManyWrongAttempts(AimHarderErrorResponse):
    key_phrase = "demasiadas veces"
