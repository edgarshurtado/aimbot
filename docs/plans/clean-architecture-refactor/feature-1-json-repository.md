# Feature 1 — JsonRepository Adapter

Implements `IUserRepository` and `IBookingRepository` on a single JSON file.

---

### Task 1.1: Write failing tests for JsonRepository

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- `JsonRepository` implements both `IUserRepository` and `IBookingRepository` on the same JSON file
- All methods return domain objects (`User`, `BookingGoal`), never raw dicts
- `BookingGoal.booking_date` serialization: persists as `"DD-MM-YYYY HH:MM"` string, deserializes to `datetime` on read
- Format constant: `_DATETIME_FMT = "%d-%m-%Y %H:%M"`
- `get_user(user_id) -> User | None`
- `get_all_users() -> list[User]`
- `get_user_bookings(user_id) -> list[BookingGoal]`
- `add_booking_goal(user_id, goal) -> Result` — returns `Result(success=False, error=UserNotFound())` for unknown user
- Dedup logic in `add_booking_goal`: if a goal with the same `(booking_date, name)` already exists, update the `job_id` in-place rather than creating a duplicate (supports startup recovery)
- `remove_booking_goal(user_id, job_id)` — removes goal by job_id
- `find_booking_goal(user_id, booking_date, class_name) -> BookingGoal | None`

**Files:**
- Create: `src/tests/test_json_repository.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_get_user_returns_domain_user_object` | Call `get_user(66666666)` on repo loaded from `test_schedule.json` (has user with id=66666666, email="some-email@gmail.com") | Returns `User` instance with `id=66666666`, `email="some-email@gmail.com"`, `password="password"`, `booking_goals=[]`. Type assertion: `isinstance(result, User)` |
| `test_get_user_returns_none_for_unknown_user` | Call `get_user(99999999)` | Returns `None` |
| `test_get_all_users_returns_list_of_user_objects` | Call `get_all_users()` | Returns `list[User]` with at least one User. Each element passes `isinstance(u, User)` |
| `test_get_user_bookings_returns_empty_list` | Call `get_user_bookings(66666666)` on user with no goals | Returns `[]` |
| `test_get_user_bookings_returns_booking_goal_objects` | Add a booking goal first via `add_booking_goal()`, then call `get_user_bookings(66666666)` | Returns `list[BookingGoal]`. Each element passes `isinstance(bg, BookingGoal)`. `booking_date` is a `datetime` object, not a string |
| `test_add_booking_goal_succeeds_for_known_user` | Call `add_booking_goal(66666666, BookingGoal(booking_date=datetime(2027, 1, 18, 18, 30), name="WOD", job_id="test-job-1"))` | Returns `Result` with `success=True`. Subsequent `get_user_bookings(66666666)` contains a BookingGoal with `name="WOD"`, `booking_date=datetime(2027, 1, 18, 18, 30)`, `job_id="test-job-1"` |
| `test_add_booking_goal_fails_for_unknown_user` | Call `add_booking_goal(99999999, BookingGoal(...))` | Returns `Result` with `success=False`, `error` is `UserNotFound` instance |
| `test_add_booking_goal_dedup_updates_job_id` | Add goal with `(booking_date=datetime(2027, 3, 15, 10, 0), name="OPEN", job_id="old-job")`. Then add another with same `booking_date` and `name` but `job_id="new-job"` | User has exactly 1 booking goal (not 2). Its `job_id == "new-job"` |
| `test_remove_booking_goal` | Add goal with `job_id="to-remove"`, then `remove_booking_goal(66666666, "to-remove")` | `get_user_bookings(66666666)` does not contain a goal with `job_id="to-remove"` |
| `test_find_booking_goal_found` | Add goal with `booking_date=datetime(2027, 5, 20, 9, 0)`, `name="WOD"`, `job_id="find-me"`. Call `find_booking_goal(66666666, datetime(2027, 5, 20, 9, 0), "WOD")` | Returns `BookingGoal` with `job_id="find-me"` |
| `test_find_booking_goal_not_found` | Call `find_booking_goal(66666666, datetime(2099, 1, 1, 0, 0), "NONEXISTENT")` | Returns `None` |
| `test_datetime_serialization_roundtrip` | Add goal with `booking_date=datetime(2027, 12, 25, 14, 30)`. Read back from a fresh `JsonRepository` instance (re-load from disk) | `booking_date == datetime(2027, 12, 25, 14, 30)` — proves it survived JSON serialization/deserialization as a datetime, not a string |

**Data structures referenced:**
- `domain.models.User(id: int, email: str, password: str, booking_goals: list[BookingGoal])`
- `domain.models.BookingGoal(booking_date: datetime, name: str, job_id: str)`
- `error_handling.Result(success: bool, data=None, error=None)`
- `error_handling.UserNotFound`

**Setup:**
- Use `test_schedule.json` as the backing file (same as existing tests)
- Use pytest fixtures: a `repository` fixture that creates `JsonRepository('test_schedule.json')` and cleans up booking goals after each test (via `yield` + teardown)
- All mocking uses the `mocker` fixture from pytest-mock (no `unittest.mock` imports)

**Key assertions:**
- Every method returning domain data must be type-checked with `isinstance()` — this is the primary contract change (raw dicts -> domain objects)
- `booking_date` fields must be `datetime` instances, never strings
- Dedup test must assert count == 1 AND the job_id was updated

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_json_repository.py -v`
Expected: ALL tests FAIL (class `JsonRepository` at new path not found, or methods don't exist yet)

**Commit:** `git commit -m "test: add failing tests for JsonRepository adapter"`

---

### Task 1.2: Implement JsonRepository

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 1.1 must be complete (failing tests must exist)

**Goal:** Write the minimal code to make ALL tests from Task 1.1 pass. Do NOT add functionality beyond what the tests require. YAGNI.

**Files:**
- Create: `src/infrastructure/persistence/json_repository.py`
- Reference: `src/tests/test_json_repository.py` (already exists from 1.1)

**What to implement:**

`JsonRepository` class implementing `IUserRepository` and `IBookingRepository`:

```python
class JsonRepository(IUserRepository, IBookingRepository):
    _DATETIME_FMT = "%d-%m-%Y %H:%M"

    def __init__(self, db_file_name: str = "schedule.json") -> None
    def get_user(self, user_id: int) -> User | None
    def get_all_users(self) -> list[User]
    def get_user_bookings(self, user_id: int) -> list[BookingGoal]
    def add_booking_goal(self, user_id: int, goal: BookingGoal) -> Result
    def remove_booking_goal(self, user_id: int, job_id: str) -> None
    def find_booking_goal(self, user_id: int, booking_date: datetime, class_name: str) -> BookingGoal | None
```

**Internal mapping logic (dict <-> domain):**
- On read: convert raw JSON dicts to `User` and `BookingGoal` objects. Parse `booking_goal["datetime"]` string to `datetime` via `_DATETIME_FMT`.
- On write: convert `BookingGoal.booking_date` to string via `_DATETIME_FMT` before persisting. Store as `{"datetime": "DD-MM-YYYY HH:MM", "name": "...", "job_id": "..."}`.

**Behavioral rules:**
- `add_booking_goal` dedup: match on `(booking_date, name)`. If match found, update `job_id` in-place. If no match, append.
- The JSON file structure is: `[{"user": {...}, "bookingGoals": [...], "recurrentBookingGoals": {...}}, ...]`
- File path resolution: same as existing `src/repository.py` — `os.path.dirname(os.path.abspath(__file__))` joined with `db_file_name`. **Note:** since the new file lives in `src/infrastructure/persistence/`, the `db_file_name` path must resolve relative to the `src/` directory (where `schedule.json` lives), not relative to the module file. Use the same approach as the old repo or accept an absolute/relative path.
- `get_user` returns a deep copy (prevents callers from mutating internal state)

**Error handling:**

| Condition | Error Type | Response |
|-----------|-----------|----------|
| `add_booking_goal` for unknown user_id | `UserNotFound` | `Result(success=False, error=UserNotFound())` |
| `get_user` for unknown user_id | N/A | Returns `None` |
| `find_booking_goal` for unknown combo | N/A | Returns `None` |

**DI registration table:** N/A — no DI container in this project. `JsonRepository` is instantiated directly in the composition root (`main.py`).

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_json_repository.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement JsonRepository adapter for IUserRepository and IBookingRepository"`

---

### Task 1.3: Adversarial review of JsonRepository

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 1.2 must be complete (implementation must exist and tests pass)

**Your role:** You are an adversarial reviewer with TWO equally important jobs:
1. **Verify requirements** — confirm the implementation actually delivers what was specified. Bug-free code that doesn't follow the requirements is a FAIL.
2. **Break it** — find bugs, edge cases, and gaps. Assume the implementation is wrong until proven otherwise.

**Design requirements to verify:**
- `JsonRepository` implements both `IUserRepository` and `IBookingRepository` (class inherits from both ABCs)
- All public methods return domain objects (`User`, `BookingGoal`), never raw dicts
- `BookingGoal.booking_date` is serialized as `"DD-MM-YYYY HH:MM"` string in JSON, deserialized to `datetime` on read
- Format constant `_DATETIME_FMT = "%d-%m-%Y %H:%M"` is used consistently
- Dedup in `add_booking_goal`: same `(booking_date, name)` -> update `job_id`, don't duplicate
- `add_booking_goal` returns `Result(success=False, error=UserNotFound())` for unknown user
- `get_user` returns deep copy, not a reference to internal data

**Review checklist:**

1. **Requirements compliance** — Read the implementation and compare against EACH requirement above. Treat them as a checklist.
2. **Completeness** — Are ALL required methods present with correct signatures?
3. **Test adequacy** — Could the tests pass with a wrong implementation? Try: what if `get_user` returned a dict instead of `User` — would any test catch it? (The `isinstance` checks should.)
4. **Edge cases** — Try to break it:
   - What if two goals have the same `name` but different `booking_date`? They should NOT dedup.
   - What if two goals have the same `booking_date` but different `name`? They should NOT dedup.
   - What if `remove_booking_goal` is called with a `job_id` that doesn't exist? Should not crash.
   - What if the JSON file has a user with `bookingGoals` containing entries with malformed datetime strings?
5. **Error handling** — What happens with concurrent access? (Not a requirement, but worth noting.)
6. **Integration** — Does the new repository work with the same `test_schedule.json` file format?

**If FAIL:** Create fix tasks. **If additional tests written:** commit them.

**Commit:** `git commit -m "test: add adversarial tests for JsonRepository"`
