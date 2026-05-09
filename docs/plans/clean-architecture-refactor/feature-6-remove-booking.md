# Feature 6 — RemoveBookingUseCase

Application layer use case that removes a scheduled booking.

---

### Task 6.1: Write failing tests for RemoveBookingUseCase

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- Dependencies: `IBookingRepository`, `IJobScheduler`
- `execute(user_id: int, job_id: str) -> None`
- Step 1: `scheduler.remove_job(job_id)`
- Step 2: `booking_repo.remove_booking_goal(user_id, job_id)`

**Files:**
- Create: `src/tests/use_cases/test_remove_booking.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_remove_booking_removes_job_and_goal` | Call `execute(user_id=123, job_id="job-abc")` | `scheduler.remove_job` called with `"job-abc"`. `booking_repo.remove_booking_goal` called with `(123, "job-abc")` |
| `test_remove_booking_calls_scheduler_before_repo` | Call `execute(user_id=123, job_id="job-xyz")` | `scheduler.remove_job` is called BEFORE `booking_repo.remove_booking_goal` (verify call order) |
| `test_remove_booking_propagates_scheduler_error` | `scheduler.remove_job` raises `JobLookupError` (or any exception) | Exception propagates. `booking_repo.remove_booking_goal` NOT called (job removal failed, don't remove the record) |

**Data structures referenced:**
- `domain.ports.booking_repository.IBookingRepository`
- `domain.ports.scheduler.IJobScheduler`

**Setup:**
- Two dependencies mocked via pytest-mock: `mocker.Mock(spec=IBookingRepository)`, `mocker.Mock(spec=IJobScheduler)`
- Use a pytest fixture that creates the use case with mocked dependencies:
  ```python
  @pytest.fixture
  def remove_booking(mocker):
      booking_repo = mocker.Mock(spec=IBookingRepository)
      scheduler = mocker.Mock(spec=IJobScheduler)
      uc = RemoveBookingUseCase(booking_repo, scheduler)
      return uc, booking_repo, scheduler
  ```

**Key assertions:**
- Both methods called with the correct arguments
- Order matters: scheduler first, then repo (if scheduler fails, we don't lose the persisted goal)
- If scheduler raises, repo is NOT called

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/use_cases/test_remove_booking.py -v`
Expected: ALL tests FAIL (module not found)

**Commit:** `git commit -m "test: add failing tests for RemoveBookingUseCase"`

---

### Task 6.2: Implement RemoveBookingUseCase

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 6.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 6.1 pass.

**Files:**
- Create: `src/application/use_cases/remove_booking.py`
- Reference: `src/tests/use_cases/test_remove_booking.py`

**What to implement:**

```python
class RemoveBookingUseCase:
    def __init__(
        self,
        booking_repo: IBookingRepository,
        scheduler: IJobScheduler,
    ) -> None

    def execute(self, user_id: int, job_id: str) -> None
```

**`execute` logic:**
1. `self._scheduler.remove_job(job_id)`
2. `self._booking_repo.remove_booking_goal(user_id, job_id)`

**Behavioral rules:**
- Scheduler removal first — if it fails, don't touch the repo (the job still exists)
- No error handling — exceptions propagate to the caller

**DI registration table:** N/A

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/use_cases/test_remove_booking.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement RemoveBookingUseCase"`

---

### Task 6.3: Adversarial review of RemoveBookingUseCase

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 6.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- Dependencies: exactly `IBookingRepository` and `IJobScheduler` — nothing else
- 2-step sequence: remove job, then remove goal
- Scheduler error propagates (goal not removed if job removal fails)

**Review checklist:**
1. **Requirements compliance** — simple 2-step flow
2. **Test adequacy** — do tests verify operation order? Do tests verify propagation on error?
3. **Edge cases** — what if `remove_booking_goal` fails after `remove_job` succeeds? (Orphaned job removal — acceptable for now, but worth noting)
4. **Error handling** — exceptions propagate correctly?

**Commit:** `git commit -m "test: add adversarial tests for RemoveBookingUseCase"`
