# Feature 4 — ScheduleBookingUseCase

Application layer use case that schedules a future booking.

---

### Task 4.1: Write failing tests for ScheduleBookingUseCase

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- Dependencies: `IUserRepository`, `IBookingRepository`, `IJobScheduler`, `IGymPlatformConfig`
- Does NOT depend on `ExecuteBookingUseCase`
- `execute(user_id: int, booking_date: datetime, class_name: str) -> None`
- Step 1: Verify user exists via `user_repo.get_user(user_id)` — raise/error if None
- Step 2: Compute trigger time via `platform_config.booking_trigger_time(booking_date)`
- Step 3: Schedule job via `scheduler.schedule_job(run_at=trigger, user_id=user_id, booking_date=booking_date, class_name=class_name)` — returns `job_id`
- Step 4: Persist via `booking_repo.add_booking_goal(user_id, BookingGoal(booking_date, class_name, job_id))`

**Files:**
- Create: `src/tests/use_cases/test_schedule_booking.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_schedule_booking_creates_job_and_persists_goal` | `user_repo.get_user(123)` returns `User(id=123, email="a@b.com", password="pw")`. `platform_config.booking_trigger_time(datetime(2027, 3, 15, 18, 30))` returns `datetime(2027, 3, 12, 18, 30)`. `scheduler.schedule_job(...)` returns `"job-abc"`. Call `use_case.execute(user_id=123, booking_date=datetime(2027, 3, 15, 18, 30), class_name="WOD")` | `scheduler.schedule_job` called with `run_at=datetime(2027, 3, 12, 18, 30)`, `user_id=123`, `booking_date=datetime(2027, 3, 15, 18, 30)`, `class_name="WOD"`. `booking_repo.add_booking_goal` called with `user_id=123` and `BookingGoal(booking_date=datetime(2027, 3, 15, 18, 30), name="WOD", job_id="job-abc")` |
| `test_schedule_booking_user_not_found` | `user_repo.get_user(999)` returns `None`. Call `execute(user_id=999, ...)` | Raises an exception (or returns error). `scheduler.schedule_job` NOT called. `booking_repo.add_booking_goal` NOT called |
| `test_schedule_booking_uses_platform_trigger_time` | `platform_config.booking_trigger_time(datetime(2027, 6, 10, 10, 0))` returns `datetime(2027, 6, 7, 10, 0)`. Call `execute(...)` | `scheduler.schedule_job` called with `run_at=datetime(2027, 6, 7, 10, 0)` — proving it delegates to `platform_config`, not hardcoding |
| `test_schedule_booking_passes_job_id_to_booking_goal` | `scheduler.schedule_job` returns `"unique-id-42"` | `booking_repo.add_booking_goal` called with goal whose `job_id == "unique-id-42"` |
| `test_schedule_booking_does_not_depend_on_execute_use_case` | Inspect the `__init__` signature of `ScheduleBookingUseCase` | No parameter for `ExecuteBookingUseCase` or any execute-related dependency |

**Data structures referenced:**
- `domain.models.User`, `domain.models.BookingGoal`
- `domain.ports.user_repository.IUserRepository`
- `domain.ports.booking_repository.IBookingRepository`
- `domain.ports.scheduler.IJobScheduler`
- `domain.ports.gym_client.IGymPlatformConfig`

**Setup:**
- All four dependencies mocked via pytest-mock: `mocker.Mock(spec=IUserRepository)`, `mocker.Mock(spec=IBookingRepository)`, `mocker.Mock(spec=IJobScheduler)`, `mocker.Mock(spec=IGymPlatformConfig)`
- Use a pytest fixture that creates the use case with mocked dependencies:
  ```python
  @pytest.fixture
  def schedule_booking(mocker):
      user_repo = mocker.Mock(spec=IUserRepository)
      booking_repo = mocker.Mock(spec=IBookingRepository)
      scheduler = mocker.Mock(spec=IJobScheduler)
      platform_config = mocker.Mock(spec=IGymPlatformConfig)
      uc = ScheduleBookingUseCase(user_repo, booking_repo, scheduler, platform_config)
      return uc, user_repo, booking_repo, scheduler, platform_config
  ```

**Key assertions:**
- The order of operations matters: get_user BEFORE schedule_job BEFORE add_booking_goal
- `booking_trigger_time` is called with the `booking_date`, not some other date
- The `BookingGoal` passed to `add_booking_goal` uses the `job_id` returned by `schedule_job`
- No mock for `ExecuteBookingUseCase` is needed — proving decoupling

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/use_cases/test_schedule_booking.py -v`
Expected: ALL tests FAIL (module not found)

**Commit:** `git commit -m "test: add failing tests for ScheduleBookingUseCase"`

---

### Task 4.2: Implement ScheduleBookingUseCase

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 4.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 4.1 pass.

**Files:**
- Create: `src/application/use_cases/schedule_booking.py`
- Reference: `src/tests/use_cases/test_schedule_booking.py`

**What to implement:**

```python
class ScheduleBookingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        booking_repo: IBookingRepository,
        scheduler: IJobScheduler,
        platform_config: IGymPlatformConfig,
    ) -> None

    def execute(self, user_id: int, booking_date: datetime, class_name: str) -> None
```

**`execute` logic:**
1. `user = self._user_repo.get_user(user_id)` — if `None`, raise `ValueError` (or a domain exception)
2. `trigger = self._platform_config.booking_trigger_time(booking_date)`
3. `job_id = self._scheduler.schedule_job(run_at=trigger, user_id=user_id, booking_date=booking_date, class_name=class_name)`
4. `self._booking_repo.add_booking_goal(user_id, BookingGoal(booking_date=booking_date, name=class_name, job_id=job_id))`

**Error handling:**

| Condition | Error Type | Response |
|-----------|-----------|----------|
| `get_user` returns `None` | `ValueError` or domain exception | Raised before scheduling |

**Behavioral rules:**
- Operations execute in strict order: verify user -> compute trigger -> schedule -> persist
- No dependency on `ExecuteBookingUseCase`

**DI registration table:** N/A

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/use_cases/test_schedule_booking.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement ScheduleBookingUseCase"`

---

### Task 4.3: Adversarial review of ScheduleBookingUseCase

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 4.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- Dependencies: exactly `IUserRepository`, `IBookingRepository`, `IJobScheduler`, `IGymPlatformConfig` — no others
- Does NOT depend on `ExecuteBookingUseCase`
- `execute(user_id, booking_date, class_name)` follows the 4-step sequence exactly
- User verification happens BEFORE any scheduling
- `booking_trigger_time` receives `booking_date` (not some modified date)
- `job_id` from scheduler is correctly passed to `BookingGoal`

**Review checklist:**
1. **Requirements compliance** — each step implemented correctly
2. **Test adequacy** — do tests verify the ORDER of operations? What if persist happens before schedule?
3. **Edge cases** — what if `schedule_job` raises? Is the goal still persisted? (It shouldn't be.)
4. **Error handling** — is `user_not_found` case handled before any side effects?

**Commit:** `git commit -m "test: add adversarial tests for ScheduleBookingUseCase"`
