# Feature 3 — APSchedulerAdapter

Thin APScheduler wrapper implementing `IJobScheduler`. Uses `DateTrigger` only (no cron). Job execution handler injected at construction time.

---

### Task 3.1: Write failing tests for APSchedulerAdapter

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- `APSchedulerAdapter` implements `IJobScheduler`
- Constructor takes `on_job_execute: Callable[[int, datetime, str], None]` — the handler called when a job fires
- `schedule_job(run_at, user_id, booking_date, class_name) -> str` — returns a job_id string, schedules a `DateTrigger` job
- `remove_job(job_id)` — removes a scheduled job
- `start()` — starts the underlying scheduler
- No booking logic in the adapter — it just translates to APScheduler calls
- Only serializable data crosses the boundary: `user_id: int`, `booking_date: datetime`, `class_name: str`

**Files:**
- Create: `src/tests/test_apscheduler_adapter.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_implements_ischeduler` | Create `APSchedulerAdapter(on_job_execute=Mock())` | `isinstance(adapter, IJobScheduler)` is `True` |
| `test_schedule_job_returns_job_id` | Call `adapter.schedule_job(run_at=datetime(2027, 3, 12, 18, 30), user_id=123, booking_date=datetime(2027, 3, 15, 18, 30), class_name="WOD")` | Returns a non-empty string (the job_id) |
| `test_schedule_job_creates_date_trigger` | Schedule a job and inspect the underlying APScheduler | The job's trigger is a `DateTrigger` with `run_date == datetime(2027, 3, 12, 18, 30)` |
| `test_scheduled_job_calls_handler_with_correct_args` | Schedule a job with `run_at` in the immediate past (or use APScheduler's test utilities). Use a `Mock` as `on_job_execute` | The handler mock is called with `(123, datetime(2027, 3, 15, 18, 30), "WOD")` — the `user_id`, `booking_date`, and `class_name` passed to `schedule_job`, NOT the `run_at` |
| `test_remove_job_removes_scheduled_job` | Schedule a job, get `job_id`, then `adapter.remove_job(job_id)` | Job no longer exists in the scheduler. Calling `remove_job` again raises `JobLookupError` (APScheduler behavior) |
| `test_start_starts_scheduler` | Call `adapter.start()` | The underlying `BackgroundScheduler.start()` was called (mock or spy) |
| `test_schedule_job_unique_ids` | Schedule two different jobs | Returns two different `job_id` strings |

**Data structures referenced:**
- `domain.ports.scheduler.IJobScheduler`
- `apscheduler.triggers.date.DateTrigger`

**Setup:**
- Use a pytest fixture that creates `APSchedulerAdapter(on_job_execute=mocker.Mock())` using the `mocker` fixture from pytest-mock
- For the handler invocation test: either schedule with a past `run_at` and call `start()`, or use `mocker.patch` on the APScheduler internals to verify the args passed to `add_job`
- All mocking uses the `mocker` fixture (no `unittest.mock` imports)

**Key assertions:**
- `schedule_job` passes `[user_id, booking_date, class_name]` as job args, NOT `run_at`
- `on_job_execute` is the actual function passed to APScheduler's `add_job`, not wrapped in another lambda
- Job trigger type is `DateTrigger`, NOT `CronTrigger`

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_apscheduler_adapter.py -v`
Expected: ALL tests FAIL (class not found)

**Commit:** `git commit -m "test: add failing tests for APSchedulerAdapter"`

---

### Task 3.2: Implement APSchedulerAdapter

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 3.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 3.1 pass.

**Files:**
- Create: `src/infrastructure/scheduling/apscheduler.py`
- Reference: `src/tests/test_apscheduler_adapter.py`

**What to implement:**

```python
class APSchedulerAdapter(IJobScheduler):
    def __init__(self, on_job_execute: Callable[[int, datetime, str], None]) -> None
    def start(self) -> None
    def schedule_job(self, run_at: datetime, user_id: int, booking_date: datetime, class_name: str) -> str
    def remove_job(self, job_id: str) -> None
```

**Implementation details:**
- Wraps `BackgroundScheduler` from APScheduler
- `schedule_job`: calls `self._scheduler.add_job(self._handler, trigger=DateTrigger(run_date=run_at), args=[user_id, booking_date, class_name])`, returns `job.id`
- `remove_job`: calls `self._scheduler.remove_job(job_id)`
- `start`: calls `self._scheduler.start()`
- The handler (`on_job_execute`) is stored at construction and passed as the callable to `add_job`

**Behavioral rules:**
- No business logic — pure delegation to APScheduler
- Only `DateTrigger` is used (no `CronTrigger`)
- The adapter does NOT know about booking repositories, gym clients, or notifications

**DI registration table:** N/A

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_apscheduler_adapter.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement APSchedulerAdapter for IJobScheduler"`

---

### Task 3.3: Adversarial review of APSchedulerAdapter

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 3.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- Implements `IJobScheduler` interface
- Constructor takes `on_job_execute: Callable[[int, datetime, str], None]`
- `schedule_job` uses `DateTrigger`, NOT `CronTrigger`
- `schedule_job` passes `[user_id, booking_date, class_name]` as args (not `run_at`)
- Returns `job.id` as string
- No business logic — pure APScheduler delegation

**Review checklist:**
1. **Requirements compliance** — verify each requirement
2. **Test adequacy** — can tests pass if `run_at` was incorrectly included in job args?
3. **Edge cases** — what if `run_at` is in the past? APScheduler behavior?
4. **Error handling** — what if `remove_job` is called with an invalid job_id?
5. **Integration** — is the adapter truly business-logic-free?

**Commit:** `git commit -m "test: add adversarial tests for APSchedulerAdapter"`
