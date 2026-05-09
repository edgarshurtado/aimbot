# Task 0 — Scaffolding: Domain Layer (Models, Exceptions, Ports)

**Type:** Scaffolding (no triplet — pure type/interface definitions with no logic to test)
**Depends on:** None

## Rationale

The domain layer contains only dataclasses, exception classes, and abstract base classes (ports). These are pure structural definitions with no branching logic, no side effects, and no behavior to test. They exist so that all subsequent features can import the types they need. Testing them would mean asserting that Python dataclasses have fields — which is tautological.

## Prerequisites

Add `pytest-mock` to `requirements-tests.txt`:

```
pytest
pytest-mock
black
flake8
freezegun
```

Then install: `pip install -r requirements-tests.txt` (or `make venv` if it reinstalls deps).

All new tests use the `mocker` fixture from pytest-mock instead of importing from `unittest.mock`. Use `mocker.Mock(spec=...)` to create spec-constrained mocks, and `mocker.patch(...)` instead of `@patch` decorators or `with patch(...)` context managers.

## What to Create

### Directory structure

```
src/
├── domain/
│   ├── __init__.py           # empty
│   ├── models.py
│   ├── exceptions.py
│   └── ports/
│       ├── __init__.py       # empty
│       ├── user_repository.py
│       ├── booking_repository.py
│       ├── gym_client.py
│       ├── scheduler.py
│       └── notifier.py
├── application/
│   ├── __init__.py           # empty
│   └── use_cases/
│       └── __init__.py       # empty
├── infrastructure/
│   ├── __init__.py           # empty
│   ├── aimharder/
│   │   └── __init__.py       # empty
│   ├── persistence/
│   │   └── __init__.py       # empty
│   ├── scheduling/
│   │   └── __init__.py       # empty
│   └── telegram/
│       └── __init__.py       # empty
└── tests/
    └── use_cases/
        └── __init__.py       # empty
```

### `src/domain/models.py`

Replace the existing `src/models.py` content. Use `@dataclass` (from `dataclasses`):

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class GymClass:
    id: str
    name: str
    time: str           # "HH:MM", normalized by the adapter
    spots_available: int
    max_spots: int

@dataclass
class BookingGoal:
    booking_date: datetime   # renamed from 'datetime' to avoid shadowing
    name: str
    job_id: str

@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: list[BookingGoal] = field(default_factory=list)
```

Key changes from old `models.py`:
- `BookingGoal.datetime` renamed to `BookingGoal.booking_date` (type: `datetime` object, not string)
- `BookingGoal.from_dict()` removed — mapping is the repository's responsibility
- `User.user_id` renamed to `User.id` (consistent with old `self.id` but now a dataclass field)
- All use `@dataclass` instead of manual `__init__`

### `src/domain/exceptions.py`

Move from `src/exceptions.py` — identical content:

```python
from abc import ABC

MESSAGE_BOOKING_FAILED_NO_CREDIT = "No credit available"
MESSAGE_BOOKING_FAILED_UNKNOWN = "Unknown error"
MESSAGE_BOX_IS_CLOSED = "Box is closed"

class ErrorResponse(ABC, Exception):
    key_phrase = None

class TooManyWrongAttempts(ErrorResponse):
    key_phrase = "demasiadas veces"

class IncorrectCredentials(ErrorResponse):
    key_phrase = "incorrecto"

class BookingFailed(Exception):
    pass

class NoBookingGoal(Exception):
    pass

class BoxClosed(Exception):
    pass
```

### `src/domain/ports/user_repository.py`

```python
from abc import ABC, abstractmethod
from domain.models import User

class IUserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_all_users(self) -> list[User]: ...
```

### `src/domain/ports/booking_repository.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
from domain.models import BookingGoal
from error_handling import Result

class IBookingRepository(ABC):
    @abstractmethod
    def get_user_bookings(self, user_id: int) -> list[BookingGoal]: ...

    @abstractmethod
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> Result: ...

    @abstractmethod
    def remove_booking_goal(self, user_id: int, job_id: str) -> None: ...

    @abstractmethod
    def find_booking_goal(self, user_id: int, booking_date: datetime, class_name: str) -> BookingGoal | None: ...
```

### `src/domain/ports/gym_client.py`

Three interfaces:

```python
from abc import ABC, abstractmethod
from datetime import datetime
from domain.models import GymClass

class IGymPlatformConfig(ABC):
    @abstractmethod
    def booking_trigger_time(self, class_date: datetime) -> datetime: ...

class IGymClient(ABC):
    @abstractmethod
    def get_classes(self, target_day: datetime) -> list[GymClass]: ...

    @abstractmethod
    def book_class(self, target_day: datetime, class_id: str) -> None: ...

class IGymClientFactory(ABC):
    @abstractmethod
    def create(self, email: str, password: str) -> IGymClient: ...
```

### `src/domain/ports/scheduler.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime

class IJobScheduler(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def schedule_job(self, run_at: datetime, user_id: int, booking_date: datetime, class_name: str) -> str: ...

    @abstractmethod
    def remove_job(self, job_id: str) -> None: ...
```

### `src/domain/ports/notifier.py`

```python
from abc import ABC, abstractmethod

class IUserNotifier(ABC):
    @abstractmethod
    def notify_user(self, user_id: int, message: str) -> None: ...

class IGroupNotifier(ABC):
    @abstractmethod
    def notify_group(self, message: str) -> None: ...
```

## Files NOT deleted yet

The old files (`src/models.py`, `src/exceptions.py`, `src/booking_scheduler.py`, `src/telegram_logger.py`, `src/main.py`) remain in place during feature development. They are deleted in Feature 9 (Composition Root + Cleanup). This avoids breaking existing tests until the migration is complete.

## Verification

```bash
PYTHONPATH=src python -c "
from domain.models import GymClass, BookingGoal, User
from domain.exceptions import BookingFailed, NoBookingGoal, BoxClosed
from domain.ports.user_repository import IUserRepository
from domain.ports.booking_repository import IBookingRepository
from domain.ports.gym_client import IGymPlatformConfig, IGymClient, IGymClientFactory
from domain.ports.scheduler import IJobScheduler
from domain.ports.notifier import IUserNotifier, IGroupNotifier
print('All domain imports OK')
"
```

Expected: prints "All domain imports OK" with no errors.

**Commit:** `git commit -m "chore: scaffold domain layer with models, exceptions, and port interfaces"`
