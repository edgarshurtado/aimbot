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
│       ├── scheduler.py            # IJobScheduler
│       └── notifier.py             # IUserNotifier, IGroupNotifier
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
│       ├── user_notifier.py        # TelegramUserNotifier (implements IUserNotifier)
│       └── group_notifier.py       # TelegramGroupNotifier (implements IGroupNotifier)
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
```python
@dataclass
class GymClass:
    id: str
    name: str
    time: str           # "HH:MM", normalized by the adapter
    spots_available: int
    max_spots: int

@dataclass
class BookingGoal:
    booking_date: datetime   # renamed from 'datetime' to avoid shadowing the type
    name: str
    job_id: str

@dataclass
class User:
    id: int
    email: str
    password: str
    booking_goals: list[BookingGoal] = field(default_factory=list)
```

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
    def find_booking_goal(self, user_id: int, booking_date: datetime, class_name: str) -> BookingGoal | None: ...
```

### `domain/ports/gym_client.py`
Split into three interfaces to cleanly separate authenticated from stateless concerns:

```python
class IGymPlatformConfig(ABC):
    """Stateless platform-level queries — no user credentials needed."""
    def booking_trigger_time(self, class_date: datetime) -> datetime: ...

class IGymClient(ABC):
    """Authenticated session — user-specific operations."""
    def get_classes(self, target_day: datetime) -> list[GymClass]: ...
    def book_class(self, target_day: datetime, class_id: str): ...

class IGymClientFactory(ABC):
    """Creates per-user authenticated clients."""
    def create(self, email: str, password: str) -> IGymClient: ...
```

`AimHarderClientFactory` implements both `IGymClientFactory` and `IGymPlatformConfig`, so a single instance satisfies both dependencies in `main.py`.

### `domain/ports/scheduler.py`
Domain-specific signature — only serializable data crosses the boundary. The handler (what to execute when the job fires) is injected into the adapter at the composition root, not passed through the port.
```python
class IJobScheduler(ABC):
    def start(self): ...
    def schedule_job(self, run_at: datetime, user_id: int, booking_date: datetime, class_name: str) -> str: ...  # returns job_id
    def remove_job(self, job_id: str): ...
```

Note: `IJobScheduler` only handles `DateTrigger` jobs (one-time bookings). The old cron scheduler for recurrent bookings is removed entirely.

### `domain/ports/notifier.py`
Two separate ports for user-facing DMs and group-channel logging:
```python
class IUserNotifier(ABC):
    def notify_user(self, user_id: int, message: str): ...

class IGroupNotifier(ABC):
    def notify_group(self, message: str): ...
```

---

## Section 2 — Application Layer (Use Cases)

### `ScheduleBookingUseCase`
**Dependencies:** `IUserRepository`, `IBookingRepository`, `IJobScheduler`, `IGymPlatformConfig`

Note: does **not** depend on `ExecuteBookingUseCase`. The composition root wires the execute handler into `APSchedulerAdapter` directly, decoupling the two use cases.

**`execute(user_id, booking_date, class_name)`**
1. Verify user exists via `IUserRepository.get_user(user_id)`
2. Compute job trigger: `trigger = gym_platform_config.booking_trigger_time(booking_date)`
3. Schedule job: `job_id = scheduler.schedule_job(run_at=trigger, user_id=user_id, booking_date=booking_date, class_name=class_name)`
4. Persist: `booking_repo.add_booking_goal(user_id, BookingGoal(booking_date, class_name, job_id))`

### `ExecuteBookingUseCase`
**Dependencies:** `IUserRepository`, `IBookingRepository`, `IGymClientFactory`, `IUserNotifier`, `IGroupNotifier`

**`execute(user_id, booking_date, class_name)`**
1. Fetch user: `user_repo.get_user(user_id)`
2. Create gym client: `client = gym_client_factory.create(user.email, user.password)`
3. Get classes: `classes = client.get_classes(booking_date)` — returns `list[GymClass]`
4. Find and book: match `GymClass` by time + name, call `client.book_class(booking_date, gym_class.id)`
5. Clean up: `goal = booking_repo.find_booking_goal(user_id, booking_date, class_name)`, then `booking_repo.remove_booking_goal(user_id, goal.job_id)` if found
6. Notify: `self._user_notifier.notify_user(user_id, ...)` and `self._group_notifier.notify_group(...)`

`booking_date` IS the target booking day — no `days_in_advance` needed here, because the job fires exactly when the booking window opens.

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
`JsonRepository` implements both `IUserRepository` and `IBookingRepository` on the same JSON file. All internal dict ↔ domain object mapping is encapsulated here — no raw dicts escape.

Handles `BookingGoal.booking_date` serialization: persists as `"DD-MM-YYYY HH:MM"` string (matching the existing `schedule.json` format), deserializes to `datetime` objects on read. The format constant is defined once: `_DATETIME_FMT = "%d-%m-%Y %H:%M"`.

Retains dedup logic in `add_booking_goal`: if a goal with the same `(booking_date, name)` already exists, it updates the `job_id` in-place rather than creating a duplicate. This exists specifically to support startup recovery — every restart re-schedules persisted goals, which produces new APScheduler `job_id` values (since the in-memory job store doesn't survive restarts).

### `infrastructure/scheduling/apscheduler.py`
Thin APScheduler wrapper using `DateTrigger` only (no cron). No booking logic — just translates `schedule_job` / `remove_job` / `start` to APScheduler calls. The job execution handler (`ExecuteBookingUseCase.execute`) is injected at construction time via `on_job_execute: Callable`, so the adapter only passes serializable data (`user_id`, `booking_date`, `class_name`) to APScheduler job args.

```python
class APSchedulerAdapter(IJobScheduler):
    def __init__(self, on_job_execute: Callable[[int, datetime, str], None]):
        self._handler = on_job_execute
        self._scheduler = BackgroundScheduler()

    def schedule_job(self, run_at, user_id, booking_date, class_name) -> str:
        job = self._scheduler.add_job(
            self._handler,
            trigger=DateTrigger(run_date=run_at),
            args=[user_id, booking_date, class_name],
        )
        return job.id
```

### `infrastructure/telegram/bot.py`
Thin UI handlers only. Injected with `ScheduleBookingUseCase`, `RemoveBookingUseCase`, and `IUserRepository` (for authorization checks and listing bookings). Handlers parse Telegram input, call use cases, and format responses — no business logic inline.

### `infrastructure/telegram/user_notifier.py`
`TelegramUserNotifier` implements `IUserNotifier`. Wraps `TelegramBot.send_message` to send booking confirmations to individual users via DM.

### `infrastructure/telegram/group_notifier.py`
`TelegramGroupNotifier` implements `IGroupNotifier`. Extracted from the old `TelegramLogger`. Sends messages to the group channel via HTTP POST. No dependency on the Telegram bot library.

---

## Section 4 — `main.py` (Composition Root)

Pure wiring — no logic, no loops beyond startup recovery:

```python
if __name__ == "__main__":
    json_repo      = JsonRepository()
    factory        = AimHarderClientFactory(box_id, box_name)

    telegram_bot   = TelegramBot(...)   # created early so notifiers can reference it
    user_notifier  = TelegramUserNotifier(telegram_bot)
    group_notifier = TelegramGroupNotifier()

    execute_uc     = ExecuteBookingUseCase(json_repo, json_repo, factory, user_notifier, group_notifier)
    apscheduler    = APSchedulerAdapter(on_job_execute=execute_uc.execute)
    schedule_uc    = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, factory)
    remove_uc      = RemoveBookingUseCase(json_repo, apscheduler)

    telegram_bot.set_use_cases(schedule_uc, remove_uc)  # deferred injection

    # Recover pending bookings after restart.
    # schedule_uc.execute() re-persists goals with updated job_ids via dedup
    # in add_booking_goal — this is expected since APScheduler's in-memory
    # job store doesn't survive restarts.
    for user in json_repo.get_all_users():
        for goal in user.booking_goals:
            schedule_uc.execute(
                user_id=user.id,
                booking_date=goal.booking_date,
                class_name=goal.name,
            )

    apscheduler.start()
    telegram_bot.run()
```

Recurrent booking code (APScheduler cron jobs, `schedule_recurrent_execution`, `load_user_schedule`) is deleted entirely.

---

## Section 5 — Testing Strategy

All tests use **pytest** with **pytest-mock** for mocking and `freezegun` for time control. Mocks are created via the `mocker` fixture (`mocker.Mock(spec=...)`) rather than importing from `unittest.mock` directly.

### New: Use Case Tests
```
tests/use_cases/
├── test_schedule_booking.py
├── test_remove_booking.py
└── test_execute_booking.py
```

Each use case test mocks the ports (`IUserRepository`, `IBookingRepository`, `IJobScheduler`, `IGymClientFactory`, `IGymPlatformConfig`, `IUserNotifier`, `IGroupNotifier`) and verifies the use case's behavior in isolation — no file I/O, no HTTP, no Telegram.

Example:
```python
def test_schedule_booking_creates_job_and_persists_goal(mocker):
    mock_user_repo    = mocker.Mock(spec=IUserRepository)
    mock_booking_repo = mocker.Mock(spec=IBookingRepository)
    mock_scheduler    = mocker.Mock(spec=IJobScheduler)
    mock_platform     = mocker.Mock(spec=IGymPlatformConfig)
    # Note: no mock for ExecuteBookingUseCase — schedule does not depend on it
    ...
```

### Updated: Adapter Tests
- **`test_client.py`** — updated import paths; logic unchanged
- **`test_repository.py`** — updated to assert `User` and `BookingGoal` objects are returned (not dicts); method names updated to match new interface
- **`test_telegram_logger.py`** — updated import paths; fixture mocks `ScheduleBookingUseCase` and `RemoveBookingUseCase` instead of `BookingScheduler`

### Deleted: `test_main.py`
`get_class_to_book` and `execution` move into use cases and are covered by use case tests. `test_main.py` is deleted.
