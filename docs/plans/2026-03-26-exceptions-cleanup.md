# Design: Exceptions Cleanup

**Date:** 2026-03-26

## Problem

The exception and error handling layer has several code smells accumulated during the clean-architecture migration:

### 1. Duplication between legacy and domain exceptions

`src/exceptions.py` (legacy) and `src/domain/exceptions.py` (modern) define the same classes and constants. Both are imported by different modules — the legacy `client.py` uses `src/exceptions.py`, and the new `infrastructure/aimharder/client.py` uses `src/domain/exceptions.py`. They also diverge: the legacy `ErrorResponse` is `ABC`, has `key_phrase = None`, and defines `TooManyWrongAttempts`; the domain version has none of that.

### 2. `BoxClosed` is semantically redundant with `BookingFailed`

`BoxClosed` is raised when `get_classes()` returns an empty list. `BookingFailed` is raised when the class isn't found or the platform rejects the booking. Both mean the same thing to callers: the booking didn't happen. No consumer handles `BoxClosed` differently from `BookingFailed`. Having two exception types forces callers to catch both for no benefit.

### 3. `ErrorResponse` with `key_phrase` is infrastructure logic in the domain

`ErrorResponse` and its subclasses (`IncorrectCredentials`, `TooManyWrongAttempts`) use a `key_phrase` class attribute to pattern-match AimHarder's HTML error text. This is an AimHarder-specific parsing mechanism. The domain shouldn't know about HTML scraping strategies — it only needs to know "authentication failed."

### 4. `ValueError` used for domain errors

`ExecuteBookingUseCase` and `ScheduleBookingUseCase` raise `ValueError("User {user_id} not found")`. `ValueError` is a Python built-in with no domain meaning — it's indistinguishable from any other validation error. Meanwhile, `error_handling.py` defines `UserNotFound(Error)` for the `Result` pattern, creating two parallel mechanisms for the same concept.

### 5. Dual error strategies (Result + exceptions) without clear boundaries

`IBookingRepository.add_booking_goal` returns `Result(success=False, error=UserNotFound())` for unknown users, but use cases raise exceptions for the same condition. The codebase uses two error mechanisms without a clear rule for when to use which.

## Current state

```
src/exceptions.py                  (legacy — used by src/client.py)
├── MESSAGE_BOOKING_FAILED_NO_CREDIT
├── MESSAGE_BOOKING_FAILED_UNKNOWN
├── MESSAGE_BOX_IS_CLOSED
├── ErrorResponse(ABC, Exception)  ← key_phrase = None
│   ├── TooManyWrongAttempts       ← key_phrase = "demasiadas veces"
│   └── IncorrectCredentials       ← key_phrase = "incorrecto"
├── BookingFailed
└── BoxClosed

src/domain/exceptions.py           (modern — used by domain & infrastructure)
├── MESSAGE_BOOKING_FAILED_NO_CREDIT
├── MESSAGE_BOOKING_FAILED_UNKNOWN
├── MESSAGE_BOX_IS_CLOSED
├── MESSAGE_GYM_CLASS_NOT_FOUND
├── ErrorResponse(Exception)       ← no key_phrase
│   └── IncorrectCredentials       ← key_phrase = "Wrong email and/or password"
├── BookingFailed
└── BoxClosed

src/error_handling.py
├── Result[R, E]
├── Error
└── UserNotFound(Error)
```

## Design

### Domain exceptions (`domain/exceptions.py`)

The domain layer defines only the exceptions that domain and application code need to raise and catch. No infrastructure-specific attributes (`key_phrase`), no HTML parsing logic.

```python
# domain/exceptions.py

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
```

Changes:
- **`BoxClosed` merged into `BookingFailed`** — callers use `BookingFailed(MESSAGE_BOX_IS_CLOSED)` instead of `BoxClosed(MESSAGE_BOX_IS_CLOSED)`. The message distinguishes the reason.
- **`ErrorResponse` removed from domain** — it was an infrastructure parsing base class. The domain only needs `AuthenticationFailed`.
- **`IncorrectCredentials` removed from domain** — replaced by `AuthenticationFailed`.
- **`UserNotFound` promoted to a domain exception** — replaces both the `ValueError` raises in use cases and the `error_handling.UserNotFound(Error)` class.

### Infrastructure exceptions (`infrastructure/aimharder/exceptions.py`)

AimHarder-specific HTML error parsing stays in the infrastructure layer:

```python
# infrastructure/aimharder/exceptions.py

class AimHarderErrorResponse(Exception):
    """Base for errors parsed from AimHarder HTML responses."""
    key_phrase: str | None = None


class IncorrectCredentials(AimHarderErrorResponse):
    key_phrase = "incorrecto"


class TooManyWrongAttempts(AimHarderErrorResponse):
    key_phrase = "demasiadas veces"
```

These are only used inside `infrastructure/aimharder/client.py` for HTML parsing. The client catches them internally and re-raises as `AuthenticationFailed` so that callers only deal with domain exceptions.

### AimHarder client changes (`infrastructure/aimharder/client.py`)

The client translates infrastructure exceptions into domain exceptions at the boundary:

```python
from domain.exceptions import AuthenticationFailed, BookingFailed, ...
from infrastructure.aimharder.exceptions import (
    AimHarderErrorResponse,
    IncorrectCredentials,
    TooManyWrongAttempts,
)

class AimHarderClient(IGymClient):
    @staticmethod
    def _login(email: str, password: str) -> Session:
        # ... existing HTTP logic ...
        if soup is not None and soup.text:
            if IncorrectCredentials.key_phrase in soup.text:
                raise AuthenticationFailed(soup.text)
            if TooManyWrongAttempts.key_phrase in soup.text:
                raise AuthenticationFailed(soup.text)
            raise AuthenticationFailed(soup.text)
        return session
```

`IncorrectCredentials` and `TooManyWrongAttempts` are still defined for potential internal use or logging, but the client raises `AuthenticationFailed` to callers. The `key_phrase` matching stays as the parsing mechanism, but it doesn't leak beyond this module.

### Use case changes

```python
# application/use_cases/execute_booking.py
from domain.exceptions import BookingFailed, UserNotFound, MESSAGE_BOX_IS_CLOSED, MESSAGE_GYM_CLASS_NOT_FOUND

class ExecuteBookingUseCase:
    def execute(self, user_id: int, booking_goal: BookingGoal) -> None:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise UserNotFound(f"User {user_id} not found")  # was ValueError

        # ...
        if not classes:
            raise BookingFailed(MESSAGE_BOX_IS_CLOSED)  # was BoxClosed

        if matched is None:
            raise BookingFailed(...)  # unchanged
```

```python
# application/use_cases/schedule_booking.py
from domain.exceptions import UserNotFound

class ScheduleBookingUseCase:
    def execute(self, user_id: int, class_start: datetime, class_name: str) -> None:
        user = self._user_repo.get_user(user_id)
        if user is None:
            raise UserNotFound(f"User {user_id} not found")  # was ValueError
```

### Repository changes (`infrastructure/persistence/json_repository.py`)

`add_booking_goal` currently returns `Result(success=False, error=UserNotFound())` using the `error_handling.py` Result pattern. Change it to raise `domain.exceptions.UserNotFound` instead, making error handling consistent with the rest of the codebase.

```python
# Before
from error_handling import Result, UserNotFound
def add_booking_goal(self, user_id, goal) -> Result:
    ...
    return Result(success=False, error=UserNotFound())

# After
from domain.exceptions import UserNotFound
def add_booking_goal(self, user_id, goal) -> None:
    ...
    raise UserNotFound(f"User {user_id} not found")
```

This changes the return type from `Result` to `None` (success) or raises (failure). The `IBookingRepository` port is updated accordingly:

```python
# domain/ports/booking_repository.py
class IBookingRepository(ABC):
    @abstractmethod
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None: ...
```

### Delete `error_handling.py`

With `UserNotFound` moved to domain exceptions and `add_booking_goal` raising instead of returning `Result`, the `error_handling.py` module (`Result`, `Error`, `UserNotFound`) becomes unused. Delete it.

### Legacy cleanup

`src/exceptions.py` and `src/client.py` are the pre-refactor legacy modules. They are not touched in this spec — they will be deleted when the legacy client is fully retired. Until then, they continue to work as-is with their own copy of exceptions.

## Target state

```
src/domain/exceptions.py
├── MESSAGE_BOOKING_FAILED_NO_CREDIT
├── MESSAGE_BOOKING_FAILED_UNKNOWN
├── MESSAGE_BOX_IS_CLOSED
├── MESSAGE_GYM_CLASS_NOT_FOUND
├── BookingFailed
├── AuthenticationFailed
└── UserNotFound

src/infrastructure/aimharder/exceptions.py  (NEW)
├── AimHarderErrorResponse
│   ├── IncorrectCredentials    ← key_phrase = "incorrecto"
│   └── TooManyWrongAttempts    ← key_phrase = "demasiadas veces"

src/error_handling.py           (DELETED)
```

## Change surface

| File | Change |
|---|---|
| `domain/exceptions.py` | Remove `ErrorResponse`, `IncorrectCredentials`, `BoxClosed`. Add `AuthenticationFailed`, `UserNotFound`. |
| `infrastructure/aimharder/exceptions.py` | **New** — `AimHarderErrorResponse`, `IncorrectCredentials`, `TooManyWrongAttempts` |
| `infrastructure/aimharder/client.py` | Import from `infrastructure/aimharder/exceptions.py`, raise `AuthenticationFailed` to callers |
| `application/use_cases/execute_booking.py` | Replace `BoxClosed` with `BookingFailed`, `ValueError` with `UserNotFound` |
| `application/use_cases/schedule_booking.py` | Replace `ValueError` with `UserNotFound` |
| `domain/ports/booking_repository.py` | `add_booking_goal` returns `None` instead of `Result` |
| `infrastructure/persistence/json_repository.py` | `add_booking_goal` raises `UserNotFound` instead of returning `Result` |
| `error_handling.py` | **Deleted** |
| Tests | Update exception types in assertions. Repository tests check `pytest.raises(UserNotFound)` instead of `result.success`. |

Untouched: `src/exceptions.py`, `src/client.py` (legacy — separate cleanup), `telegram/bot.py` (no exception handling changes in scope).
