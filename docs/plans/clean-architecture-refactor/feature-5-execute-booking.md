# Feature 5 — ExecuteBookingUseCase

Application layer use case that actually books a class when the scheduled job fires.

---

### Task 5.1: Write failing tests for ExecuteBookingUseCase

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- Dependencies: `IUserRepository`, `IBookingRepository`, `IGymClientFactory`, `IUserNotifier`, `IGroupNotifier`
- `execute(user_id: int, booking_date: datetime, class_name: str) -> None`
- Step 1: Fetch user via `user_repo.get_user(user_id)`
- Step 2: Create gym client via `gym_client_factory.create(user.email, user.password)`
- Step 3: Get classes via `client.get_classes(booking_date)` — returns `list[GymClass]`
- Step 4: Find matching class by `time` (HH:MM from booking_date) and `name` (contains class_name). Call `client.book_class(booking_date, gym_class.id)`
- Step 5: Clean up goal from repo via `find_booking_goal` + `remove_booking_goal`
- Step 6: Notify user via `user_notifier.notify_user(user_id, ...)` and group via `group_notifier.notify_group(...)`
- `booking_date` IS the target booking day — no `days_in_advance` math here

**Files:**
- Create: `src/tests/use_cases/test_execute_booking.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_execute_booking_happy_path` | User exists (id=123, email="a@b.com", pw="pw"). Factory creates a mock client. `client.get_classes(datetime(2027, 3, 15, 18, 30))` returns `[GymClass(id="42", name="WOD", time="18:30", spots_available=5, max_spots=20)]`. `booking_repo.find_booking_goal(123, datetime(2027, 3, 15, 18, 30), "WOD")` returns `BookingGoal(booking_date=datetime(2027, 3, 15, 18, 30), name="WOD", job_id="job-1")`. Call `execute(123, datetime(2027, 3, 15, 18, 30), "WOD")` | `client.book_class` called with `(datetime(2027, 3, 15, 18, 30), "42")`. `booking_repo.remove_booking_goal` called with `(123, "job-1")`. `user_notifier.notify_user` called with `(123, <message containing "WOD">)`. `group_notifier.notify_group` called with `(<message containing "WOD">)` |
| `test_execute_booking_matches_by_time_and_name` | `get_classes` returns `[GymClass(id="10", name="OPEN", time="10:00", ...), GymClass(id="20", name="WOD", time="18:30", ...), GymClass(id="30", name="WOD", time="10:00", ...)]`. Execute with `booking_date=datetime(2027, 3, 15, 18, 30)`, `class_name="WOD"` | `book_class` called with class_id `"20"` (matches both time="18:30" AND name contains "WOD") |
| `test_execute_booking_user_not_found` | `user_repo.get_user(999)` returns `None` | Raises exception. `gym_client_factory.create` NOT called |
| `test_execute_booking_no_matching_class_raises` | `get_classes` returns `[GymClass(id="10", name="OPEN", time="10:00", ...)]`. Execute with `class_name="WOD"`, `booking_date` with time 18:30 | Raises `NoBookingGoal` |
| `test_execute_booking_box_closed` | `get_classes` returns `[]` (empty list) | Raises `BoxClosed` |
| `test_execute_booking_cleans_up_goal` | Happy path with `find_booking_goal` returning a goal with `job_id="cleanup-me"` | `remove_booking_goal` called with `(user_id, "cleanup-me")` |
| `test_execute_booking_no_goal_to_clean_up` | `find_booking_goal` returns `None` | `remove_booking_goal` NOT called. No error raised. Booking still succeeds |
| `test_execute_booking_notifies_user_and_group` | Happy path | `user_notifier.notify_user` called once with `user_id=123`. `group_notifier.notify_group` called once. Both notification messages contain the class name and booking info |
| `test_execute_booking_uses_booking_date_for_get_classes` | Execute with `booking_date=datetime(2027, 6, 10, 10, 0)` | `client.get_classes` called with `datetime(2027, 6, 10, 10, 0)` — NOT `datetime.today() + timedelta(days=3)` |
| `test_execute_booking_creates_client_with_user_credentials` | User has `email="test@gym.com"`, `password="secret123"` | `factory.create` called with `("test@gym.com", "secret123")` |

**Data structures referenced:**
- `domain.models.User`, `domain.models.BookingGoal`, `domain.models.GymClass`
- `domain.ports.user_repository.IUserRepository`
- `domain.ports.booking_repository.IBookingRepository`
- `domain.ports.gym_client.IGymClientFactory`, `IGymClient`
- `domain.ports.notifier.IUserNotifier`, `IGroupNotifier`
- `domain.exceptions.NoBookingGoal`, `BoxClosed`

**Setup:**
- All five dependencies mocked via pytest-mock: `mocker.Mock(spec=IUserRepository)`, `mocker.Mock(spec=IBookingRepository)`, `mocker.Mock(spec=IGymClientFactory)`, `mocker.Mock(spec=IUserNotifier)`, `mocker.Mock(spec=IGroupNotifier)`
- Factory mock's `create` returns a `mocker.Mock(spec=IGymClient)` — the gym client mock
- Use a pytest fixture that creates the use case with mocked dependencies:
  ```python
  @pytest.fixture
  def execute_booking(mocker):
      user_repo = mocker.Mock(spec=IUserRepository)
      booking_repo = mocker.Mock(spec=IBookingRepository)
      factory = mocker.Mock(spec=IGymClientFactory)
      user_notifier = mocker.Mock(spec=IUserNotifier)
      group_notifier = mocker.Mock(spec=IGroupNotifier)
      mock_client = mocker.Mock(spec=IGymClient)
      factory.create.return_value = mock_client
      uc = ExecuteBookingUseCase(user_repo, booking_repo, factory, user_notifier, group_notifier)
      return uc, user_repo, booking_repo, factory, mock_client, user_notifier, group_notifier
  ```

**Key assertions:**
- Time matching: `booking_date`'s time component (HH:MM) is used to match against `GymClass.time`
- Name matching: `class_name` matched against `GymClass.name` (substring/contains match, consistent with existing behavior)
- `booking_date` is passed directly to `get_classes` — no `days_in_advance` arithmetic
- Cleanup is optional (no error if `find_booking_goal` returns None)
- Both notifiers are always called on success

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/use_cases/test_execute_booking.py -v`
Expected: ALL tests FAIL (module not found)

**Commit:** `git commit -m "test: add failing tests for ExecuteBookingUseCase"`

---

### Task 5.2: Implement ExecuteBookingUseCase

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 5.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 5.1 pass.

**Files:**
- Create: `src/application/use_cases/execute_booking.py`
- Reference: `src/tests/use_cases/test_execute_booking.py`

**What to implement:**

```python
class ExecuteBookingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        booking_repo: IBookingRepository,
        gym_client_factory: IGymClientFactory,
        user_notifier: IUserNotifier,
        group_notifier: IGroupNotifier,
    ) -> None

    def execute(self, user_id: int, booking_date: datetime, class_name: str) -> None
```

**`execute` logic:**
1. `user = self._user_repo.get_user(user_id)` — raise if `None`
2. `client = self._gym_client_factory.create(user.email, user.password)`
3. `classes = client.get_classes(booking_date)` — returns `list[GymClass]`
4. Find matching class:
   - Extract target time from `booking_date`: `target_time = booking_date.strftime("%H:%M")`
   - Filter `classes` where `gym_class.time == target_time` AND `class_name in gym_class.name`
   - If no classes at all: raise `BoxClosed`
   - If no matching class: raise `NoBookingGoal`
   - Call `client.book_class(booking_date, matched_class.id)`
5. Clean up:
   - `goal = self._booking_repo.find_booking_goal(user_id, booking_date, class_name)`
   - If `goal is not None`: `self._booking_repo.remove_booking_goal(user_id, goal.job_id)`
6. Notify:
   - `self._user_notifier.notify_user(user_id, f"class booked for {user.email}: {class_name} {booking_date.strftime('%H:%M')}")`
   - `self._group_notifier.notify_group(f"class booked for {user.email}: {class_name} {booking_date.strftime('%H:%M')}")`

**Error handling:**

| Condition | Error Type | Response |
|-----------|-----------|----------|
| User not found | `ValueError` | Raised before creating client |
| No classes returned (empty list) | `BoxClosed` | Raised with `MESSAGE_BOX_IS_CLOSED` |
| No matching class by time+name | `NoBookingGoal` | Raised with descriptive message |
| `book_class` fails | `BookingFailed` (from client) | Propagated — not caught here |

**Behavioral rules:**
- `booking_date` is passed directly to `get_classes` — no `days_in_advance` adjustment
- Class matching: exact time match (`==`) on `GymClass.time` vs `booking_date.strftime("%H:%M")`, substring match (`in`) on `GymClass.name` vs `class_name`
- Cleanup is optional — if `find_booking_goal` returns `None`, skip removal silently
- Both notifiers always called on successful booking

**DI registration table:** N/A

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/use_cases/test_execute_booking.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement ExecuteBookingUseCase"`

---

### Task 5.3: Adversarial review of ExecuteBookingUseCase

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 5.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- Dependencies: exactly `IUserRepository`, `IBookingRepository`, `IGymClientFactory`, `IUserNotifier`, `IGroupNotifier`
- `booking_date` IS the target day — no `days_in_advance` math
- Class matching by time (HH:MM) AND name (substring)
- Cleanup is optional (no error if goal not found)
- Both notifiers called on success
- Factory creates client with user's email and password

**Review checklist:**
1. **Requirements compliance** — 6-step flow implemented correctly
2. **Test adequacy** — do tests verify that `get_classes` receives `booking_date` (not today + offset)?
3. **Edge cases:**
   - What if multiple classes match time+name? Should book the first one (consistent with old behavior)
   - What if `book_class` raises? Are notifiers still called? (They shouldn't be)
   - What if notification fails? Should it propagate or be swallowed?
4. **Error handling** — is user-not-found checked before any external calls?
5. **Integration** — notification message format matches what Telegram handlers expect?

**Commit:** `git commit -m "test: add adversarial tests for ExecuteBookingUseCase"`
