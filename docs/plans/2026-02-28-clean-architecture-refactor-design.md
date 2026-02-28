# Clean Architecture Refactor Design

**Date:** 2026-02-28
**Status:** Approved

## Context

The current codebase has coupling issues: `telegram_logger.py` mixes UI and orchestration, `BookingScheduler` contains business logic, `main.py` duplicates booking execution, and the repository leaks raw dicts. The goal is to introduce a full clean architecture to support growth, including multi-gym support in the future.

Decisions made during design:
- Drop recurrent booking (unused feature)
- Repository returns domain objects, not raw dicts
- Ports live in the domain layer (domain owns its abstractions)
- `days_in_advance` is a platform concern, not a global constant

---

## Final Directory Structure

```
src/
├── domain/
│   ├── models.py
│   ├── exceptions.py
│   └── ports/
│       ├── user_repository.py      # IUserRepository
│       ├── booking_repository.py   # IBookingRepository
│       ├── gym_client.py           # IGymPlatformConfig, IGymClient, IGymClientFactory
│       └── scheduler.py            # IJobScheduler
│
├── application/
│   └── use_cases/
│       ├── schedule_booking.py     # ScheduleBookingUseCase
│       ├── remove_booking.py       # RemoveBookingUseCase
│       └── execute_booking.py      # ExecuteBookingUseCase
│
├── infrastructure/
│   ├── aimharder/
│   │   ├── client.py               # AimHarderClient (implements IGymClient)
│   │   └── client_factory.py       # AimHarderClientFactory (implements IGymClientFactory + IGymPlatformConfig)
│   ├── persistence/
│   │   └── json_repository.py      # JsonRepository (implements IUserRepository + IBookingRepository)
│   ├── scheduling/
│   │   └── apscheduler.py          # APSchedulerAdapter (implements IJobScheduler)
│   └── telegram/
│       ├── bot.py                  # TelegramBot — thin UI handlers only
│       └── notifier.py             # TelegramNotifier (group channel sender)
│
├── tests/
│   ├── use_cases/
│   │   ├── test_schedule_booking.py
│   │   ├── test_remove_booking.py
│   │   └── test_execute_booking.py
│   ├── test_client.py              # updated imports
│   ├── test_repository.py          # updated: asserts domain objects returned
│   └── test_telegram_logger.py     # updated: mocks use cases instead of BookingScheduler
│
├── box_data.py                     # gym config constants (composition root reads these)
├── constants.py
├── error_handling.py               # Result type utility
└── main.py                         # composition root — wiring only, no logic
```

Files deleted: `src/booking_scheduler.py`, `src/telegram_logger.py`, `src/domain/ScheduleManager.py`, `src/tests/test_main.py`

---

## Section 1 — Domain Layer

### `domain/models.py`
- `BookingGoal(datetime: datetime, name: str, job_id: str)` — typed, no raw dicts
- `User(id: int, email: str, password: str, booking_goals: list[BookingGoal])`

### `domain/exceptions.py`
All domain exceptions moved here from the root:
`NoBookingGoal`, `BoxClosed`, `BookingFailed`, `IncorrectCredentials`, `TooManyWrongAttempts`

### `domain/ports/user_repository.py`
```python
class IUserRepository(ABC):
    def get_user(self, user_id: int) -> User | None: ...
    def get_all_users(self) -> list[User]: ...   # needed on startup recovery
    # future: create_user, remove_user
```

### `domain/ports/booking_repository.py`
```python
class IBookingRepository(ABC):
    def get_user_bookings(self, user_id: int) -> list[BookingGoal]: ...
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> Result: ...
    def remove_booking_goal(self, user_id: int, job_id: str): ...
    def find_booking_goal(self, user_id: int, class_date: datetime, class_name: str) -> BookingGoal | None: ...
```

### `domain/ports/gym_client.py`
Split into three interfaces to cleanly separate authenticated from stateless concerns:

```python
class IGymPlatformConfig(ABC):
    """Stateless platform-level queries — no user credentials needed."""
    def booking_trigger_time(self, class_date: datetime) -> datetime: ...

class IGymClient(ABC):
    """Authenticated session — user-specific operations."""
    def get_classes(self, target_day: datetime) -> list[dict]: ...
    def book_class(self, target_day: datetime, class_id: str): ...

class IGymClientFactory(ABC):
    """Creates per-user authenticated clients."""
    def create(self, email: str, password: str) -> IGymClient: ...
```

`AimHarderClientFactory` implements both `IGymClientFactory` and `IGymPlatformConfig`, so a single instance satisfies both dependencies in `main.py`.

### `domain/ports/scheduler.py`
```python
class IJobScheduler(ABC):
    def start(self): ...
    def schedule_job(self, run_at: datetime, func: callable, **kwargs) -> str: ...  # returns job_id
    def remove_job(self, job_id: str): ...
```

---

## Section 2 — Application Layer (Use Cases)

### `ScheduleBookingUseCase`
**Dependencies:** `IUserRepository`, `IBookingRepository`, `IJobScheduler`, `ExecuteBookingUseCase`, `IGymPlatformConfig`

**`execute(user_id, class_date, class_name, notify: Callable[[str], None])`**
1. Verify user exists via `IUserRepository.get_user(user_id)`
2. Compute job trigger: `trigger = gym_platform_config.booking_trigger_time(class_date)`
3. Schedule job: `job_id = scheduler.schedule_job(run_at=trigger, func=execute_uc.execute, kwargs={...})`
4. Persist: `booking_repo.add_booking_goal(user_id, BookingGoal(class_date, class_name, job_id))`

### `ExecuteBookingUseCase`
**Dependencies:** `IUserRepository`, `IBookingRepository`, `IGymClientFactory`

**`execute(user_id, class_date, class_name, notify: Callable[[str], None])`**
1. Fetch user: `user_repo.get_user(user_id)`
2. Create gym client: `client = gym_client_factory.create(user.email, user.password)`
3. Get classes: `classes = client.get_classes(class_date)`
4. Find and book: locate class by time + name, call `client.book_class(class_date, class_id)`
5. Clean up: `booking_repo.remove_booking_goal(user_id, job_id)` (via `find_booking_goal`)
6. Notify: `notify(f"class booked for {user.email}: {class_name} ...")`

`class_date` IS the target booking day — no `days_in_advance` needed here, because the job fires exactly when the booking window opens.

### `RemoveBookingUseCase`
**Dependencies:** `IBookingRepository`, `IJobScheduler`

**`execute(user_id, job_id)`**
1. `scheduler.remove_job(job_id)`
2. `booking_repo.remove_booking_goal(user_id, job_id)`

---

## Section 3 — Infrastructure Adapters

### `infrastructure/aimharder/client_factory.py`
```python
class AimHarderClientFactory(IGymClientFactory, IGymPlatformConfig):
    def __init__(self, box_id: int, box_name: str):
        self._box_id = box_id
        self._box_name = box_name

    def create(self, email: str, password: str) -> AimHarderClient:
        return AimHarderClient(email, password, self._box_id, self._box_name)

    def booking_trigger_time(self, class_date: datetime) -> datetime:
        return class_date - timedelta(days=3)
```

`box_id` and `box_name` injected from `box_data.py` at the composition root.

### `infrastructure/persistence/json_repository.py`
`JsonRepository` implements both `IUserRepository` and `IBookingRepository` on the same JSON file. All internal dict ↔ domain object mapping is encapsulated here — no raw dicts escape. Retains dedup logic in `add_booking_goal` so startup recovery does not create duplicate entries.

### `infrastructure/scheduling/apscheduler.py`
Thin APScheduler wrapper. No booking logic — just translates `schedule_job` / `remove_job` / `start` to APScheduler calls.

### `infrastructure/telegram/bot.py`
Thin UI handlers only. Injected with `ScheduleBookingUseCase`, `RemoveBookingUseCase`, and `IUserRepository` (for authorization checks and listing bookings). Handlers parse Telegram input, call use cases, and format responses — no business logic inline.

### `infrastructure/telegram/notifier.py`
Extracted from the old `TelegramLogger`. Sends messages to the group channel via HTTP POST. No dependency on the Telegram bot library.

---

## Section 4 — `main.py` (Composition Root)

Pure wiring — no logic, no loops beyond startup recovery:

```python
if __name__ == "__main__":
    json_repo   = JsonRepository()
    apscheduler = APSchedulerAdapter()
    factory     = AimHarderClientFactory(box_id, box_name)

    execute_uc  = ExecuteBookingUseCase(json_repo, json_repo, factory)
    schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, execute_uc, factory)
    remove_uc   = RemoveBookingUseCase(json_repo, apscheduler)

    telegram_bot = TelegramBot(schedule_uc, remove_uc, json_repo)

    # Recover pending bookings after restart
    for user in json_repo.get_all_users():
        for goal in user.booking_goals:
            schedule_uc.execute(
                user_id=user.id,
                class_date=goal.datetime,
                class_name=goal.name,
                notify=lambda msg, uid=user.id: telegram_bot.send_message(uid, msg)
            )

    apscheduler.start()
    telegram_bot.run()
```

Recurrent booking code (APScheduler cron jobs, `schedule_recurrent_execution`, `load_user_schedule`) is deleted entirely.

---

## Section 5 — Testing Strategy

All tests use **pytest** with `unittest.mock` for mocking and `freezegun` for time control.

### New: Use Case Tests
```
tests/use_cases/
├── test_schedule_booking.py
├── test_remove_booking.py
└── test_execute_booking.py
```

Each use case test mocks the ports (`IUserRepository`, `IBookingRepository`, `IJobScheduler`, `IGymClientFactory`, `IGymPlatformConfig`) and verifies the use case's behavior in isolation — no file I/O, no HTTP, no Telegram.

Example:
```python
def test_schedule_booking_creates_job_and_persists_goal():
    mock_user_repo    = Mock(spec=IUserRepository)
    mock_booking_repo = Mock(spec=IBookingRepository)
    mock_scheduler    = Mock(spec=IJobScheduler)
    mock_platform     = Mock(spec=IGymPlatformConfig)
    mock_execute_uc   = Mock(spec=ExecuteBookingUseCase)
    ...
```

### Updated: Adapter Tests
- **`test_client.py`** — updated import paths; logic unchanged
- **`test_repository.py`** — updated to assert `User` and `BookingGoal` objects are returned (not dicts); method names updated to match new interface
- **`test_telegram_logger.py`** — updated import paths; fixture mocks `ScheduleBookingUseCase` and `RemoveBookingUseCase` instead of `BookingScheduler`

### Deleted: `test_main.py`
`get_class_to_book` and `execution` move into use cases and are covered by use case tests. `test_main.py` is deleted.
