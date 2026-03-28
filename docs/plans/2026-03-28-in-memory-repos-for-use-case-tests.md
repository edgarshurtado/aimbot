# Design: In-Memory Repositories for Use Case Tests

**Date:** 2026-03-28

## Problem

Use case tests mock every collaborator (London style), including repositories. This means:

- Tests are coupled to interaction details (`user_repo.get_user.return_value = ...`), not behavior
- Every test sets up `user_repo.get_user.return_value` even when the test isn't about user lookup
- Assertions like `booking_repo.remove_booking_goal.assert_called_once_with(...)` verify choreography, not outcomes
- If we rename `get_user` to `find_user`, every test breaks even though behavior hasn't changed

Repositories are data-holding ports with simple, deterministic logic. They don't make HTTP calls or send messages. Mocking them adds noise without adding safety.

## Design

### Hybrid testing strategy

- **Real (in-memory) implementations** for data-holding ports: `IUserRepository`, `IBookingRepository`
- **Mocks kept** for side-effecting ports: `IGymClient` (HTTP), `IGymClientFactory`, `IUserNotifier` (sends messages), `IJobScheduler` (APScheduler), `IGymConfig` (returns computed values we want to control)

### In-memory implementations

Create `src/tests/fakes.py` with two classes:

```python
from domain.exceptions import UserNotFound
from domain.models import BookingGoal, User
from domain.ports.booking_repository import IBookingRepository
from domain.ports.user_repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users = {u.id: u for u in (users or [])}

    def get_user(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def get_all_users(self) -> list[User]:
        return list(self._users.values())


class InMemoryBookingRepository(IBookingRepository):
    def __init__(self) -> None:
        self._bookings: dict[int, list[BookingGoal]] = {}

    def get_user_bookings(self, user_id: int) -> list[BookingGoal]:
        return list(self._bookings.get(user_id, []))

    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.setdefault(user_id, []).append(goal)

    def remove_booking_goal(self, user_id: int, goal: BookingGoal) -> None:
        self._bookings.get(user_id, []).remove(goal)
```

### Test changes

#### `test_execute_booking.py`

Replace mocked `user_repo` and `booking_repo` fixtures with in-memory fakes. Tests shift from interaction assertions to state assertions:

**Before (mock):**
```python
user_repo.get_user.return_value = _make_user()
# ... execute ...
booking_repo.remove_booking_goal.assert_called_once_with(123, goal)
```

**After (in-memory):**
```python
# user_repo seeded via fixture with _make_user()
# ... execute ...
assert booking_repo.get_user_bookings(123) == []  # goal was removed
```

Specific changes per test:

| Test | What changes |
|---|---|
| `happy_path` | Seed user in `InMemoryUserRepository`. Seed goal in `InMemoryBookingRepository`. Assert goal is removed after execute. Keep mock assertions for `client.book_class` and `user_notifier`. |
| `matches_by_time_and_name` | Seed user. Assert `client.book_class` called with correct class (mock stays — this is about client interaction). |
| `user_not_found` | Create `InMemoryUserRepository` with no users. Assert `UserNotFound` raised. Remove `factory.create.assert_not_called()` — if the exception is raised, the factory is obviously not called. |
| `no_matching_class_raises` | Seed user. Assert `BookingFailed`. No repo assertions needed. |
| `box_closed` | Seed user. Assert `BookingFailed`. No repo assertions needed. |
| `cleans_up_goal` | Seed user + goal. Assert `booking_repo.get_user_bookings(123) == []` after execute. |
| `notifies_user` | Seed user. Assert `user_notifier.notify_user` called with exact message (mock stays — this is a side effect). |
| `uses_class_start_for_get_classes` | Seed user. Assert `client.get_classes` called with correct datetime (mock stays). |
| `creates_client_with_user_credentials` | Seed user with specific email/password. Assert `factory.create` called with that user (mock stays — verifying factory receives correct User). |

#### `test_schedule_booking.py`

Replace mocked `user_repo` with `InMemoryUserRepository`. Keep `booking_repo` as mock since `ScheduleBookingUseCase` only calls `add_booking_goal` — but actually, we can use `InMemoryBookingRepository` here too and assert state:

| Test | What changes |
|---|---|
| `creates_job_and_persists_goal` | Seed user. Assert `booking_repo.get_user_bookings(123) == [expected_goal]`. Keep mock for `scheduler.schedule_job` (side effect). |
| `user_not_found` | Empty user repo. Assert `UserNotFound`. Assert `booking_repo.get_user_bookings(999) == []` (nothing persisted). Keep mock for `scheduler.schedule_job.assert_not_called()` (side effect). |
| `uses_platform_trigger_time` | Seed user. Keep mocks for `scheduler` and `gym_config` (side effects / computed values). |
| `does_not_depend_on_execute_use_case` | No change (introspection test, no mocks). |

#### `test_remove_booking.py`

`RemoveBookingUseCase` doesn't use `IUserRepository` at all. It calls `scheduler.remove_job` then `booking_repo.remove_booking_goal`. The scheduler is a side-effecting port (must stay mocked). The booking repo could be real:

| Test | What changes |
|---|---|
| `removes_job_and_goal` | Seed goal in `InMemoryBookingRepository`. Assert goal removed after execute. Keep mock for `scheduler.remove_job`. |
| `calls_scheduler_before_repo` | This test is specifically about call ordering between two ports. Keep both mocked — this is an interaction test by nature. |
| `propagates_scheduler_error` | Keep scheduler mocked (simulates error). Use real booking repo, assert goal still exists after failed execute. |

## Change surface

| File | Change |
|---|---|
| `tests/fakes.py` | **New** — `InMemoryUserRepository`, `InMemoryBookingRepository` |
| `tests/use_cases/test_execute_booking.py` | Replace mock repos with in-memory fakes, shift to state assertions |
| `tests/use_cases/test_schedule_booking.py` | Replace mock repos with in-memory fakes where applicable |
| `tests/use_cases/test_remove_booking.py` | Replace mock booking repo with in-memory fake where applicable |

Everything else unchanged.
