# Feature 9 — Composition Root + Old File Cleanup

Wire everything in `main.py` and delete old files.

---

### Task 9.1: Write failing tests for composition root

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Features 1-8 (all REVIEW tasks must be complete)

**Design requirements being tested:**
- `main.py` is pure wiring — no logic, no loops beyond startup recovery
- Startup recovery: iterates all users, re-schedules each user's booking goals via `schedule_uc.execute()`
- `json_repo` used as both `IUserRepository` and `IBookingRepository`
- `AimHarderClientFactory` used as both `IGymClientFactory` and `IGymPlatformConfig`
- `execute_uc.execute` injected as `on_job_execute` handler into `APSchedulerAdapter`
- `TelegramUserNotifier` wraps `telegram_bot.send_message`
- `telegram_bot.set_use_cases(schedule_uc, remove_uc)` called for deferred injection
- Recurrent booking code is deleted entirely
- Old files deleted: `src/booking_scheduler.py`, `src/telegram_logger.py`, `src/domain/ScheduleManager.py`, `src/tests/test_main.py`

**Files:**
- Create: `src/tests/test_composition_root.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_startup_recovery_reschedules_all_user_goals` | Mock all infrastructure. `json_repo.get_all_users()` returns `[User(id=1, email="a@b.com", password="pw", booking_goals=[BookingGoal(booking_date=datetime(2027, 3, 15, 18, 30), name="WOD", job_id="old-job")])]`. Execute the startup recovery logic | `schedule_uc.execute` called with `user_id=1, booking_date=datetime(2027, 3, 15, 18, 30), class_name="WOD"` |
| `test_startup_recovery_multiple_users` | Two users, each with 1-2 goals | `schedule_uc.execute` called once per goal (total 2-3 times) |
| `test_startup_recovery_no_users` | `get_all_users()` returns `[]` | `schedule_uc.execute` NOT called. No error |
| `test_apscheduler_start_called` | After startup recovery | `apscheduler.start()` is called |
| `test_execute_uc_wired_as_job_handler` | Verify that `APSchedulerAdapter` is constructed with `execute_uc.execute` as its handler | The `on_job_execute` parameter is `execute_uc.execute` |

**Setup:**
- Extract the wiring logic from `main.py` into a testable function (e.g., `create_app()` or `bootstrap()`) that returns the key objects, or test by importing and mocking the dependency construction
- Mock all external dependencies using `mocker.patch(...)` and `mocker.Mock(...)` from pytest-mock
- Use pytest fixtures to set up the mocked composition root
- All mocking uses the `mocker` fixture (no `unittest.mock` imports)

**Key assertions:**
- Startup recovery calls `schedule_uc.execute` for each `BookingGoal` in each `User`
- `schedule_uc.execute` receives `goal.booking_date` and `goal.name` (domain object fields, not dict keys)
- Order: create objects -> startup recovery -> `apscheduler.start()` -> `telegram_bot.run()`

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_composition_root.py -v`
Expected: ALL tests FAIL (composition root not yet refactored)

**Commit:** `git commit -m "test: add failing tests for composition root"`

---

### Task 9.2: Implement composition root + cleanup

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 9.1 must be complete

**Goal:** Rewrite `main.py` as pure wiring and delete old files.

**Files:**
- Modify: `src/main.py` — complete rewrite
- Delete: `src/booking_scheduler.py`
- Delete: `src/telegram_logger.py`
- Delete: `src/domain/ScheduleManager.py`
- Delete: `src/tests/test_main.py`
- Delete: `src/models.py` (replaced by `domain/models.py`)
- Delete: `src/exceptions.py` (replaced by `domain/exceptions.py`)
- Keep: `src/box_data.py`, `src/constants.py`, `src/error_handling.py`, `src/client.py` (old client kept for reference until confirmed unused — or delete if no imports remain)

**What to implement:**

New `main.py`:

```python
if __name__ == "__main__":
    json_repo      = JsonRepository()
    factory        = AimHarderClientFactory(box_id=box_id, box_name=box_name)

    telegram_bot   = TelegramBot(user_repo=json_repo)
    user_notifier  = TelegramUserNotifier(send_fn=telegram_bot.send_message)
    group_notifier = TelegramGroupNotifier()

    execute_uc     = ExecuteBookingUseCase(json_repo, json_repo, factory, user_notifier, group_notifier)
    apscheduler    = APSchedulerAdapter(on_job_execute=execute_uc.execute)
    schedule_uc    = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, factory)
    remove_uc      = RemoveBookingUseCase(json_repo, apscheduler)

    telegram_bot.set_use_cases(schedule_uc, remove_uc)

    # Startup recovery
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

**Key wiring decisions:**
- `json_repo` passed as both user_repo and booking_repo parameters (it implements both interfaces)
- `factory` used as both gym_client_factory and platform_config (it implements both interfaces)
- `execute_uc.execute` is the handler for APScheduler — when a job fires, it calls the execute use case
- `telegram_bot.send_message` is the send function for `TelegramUserNotifier`
- `set_use_cases` is deferred because `schedule_uc` depends on `apscheduler` which depends on `execute_uc` which depends on notifiers which depend on `telegram_bot`

**Cleanup:**
- Delete all listed files
- Update any remaining imports in test files if they reference old module paths
- Verify `src/tests/test_client.py` still works (it imports from `client` which may now need to import from `infrastructure.aimharder.client`)
- Update `src/tests/test_repository.py` to import from `infrastructure.persistence.json_repository` if the tests still reference the old path (or keep old tests and note they'll be replaced)

**Behavioral rules:**
- No business logic in `main.py` — only object construction and wiring
- No cron jobs, no `schedule_recurrent_execution`, no `load_user_schedule`
- The `load_dotenv()` call should remain (for environment variables)

**DI registration table:** N/A (no DI container — manual wiring)

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/ -v`
Expected: ALL tests PASS (new and surviving old tests)

**Commit:** `git commit -m "feat: implement composition root and delete legacy files"`

---

### Task 9.3: Adversarial review of composition root

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 9.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- `main.py` is pure wiring — no logic beyond startup recovery loop
- Startup recovery iterates all users and their booking goals, calls `schedule_uc.execute`
- `json_repo` satisfies both repository interfaces
- `factory` satisfies both `IGymClientFactory` and `IGymPlatformConfig`
- `execute_uc.execute` is the APScheduler handler
- Deferred injection via `set_use_cases`
- Recurrent booking code deleted entirely
- Old files deleted: `booking_scheduler.py`, `telegram_logger.py`, `domain/ScheduleManager.py`, `tests/test_main.py`

**Review checklist:**
1. **Requirements compliance** — wiring matches the design exactly
2. **Completeness** — all old files deleted, no dead imports
3. **Test adequacy** — does startup recovery test cover multiple users with multiple goals?
4. **Edge cases:**
   - What if a user's booking goal has a `booking_date` in the past? Should `schedule_uc.execute` handle it gracefully?
   - What if `schedule_uc.execute` raises during recovery? Should one failed goal skip the rest?
5. **Startup verification** — can `main.py` actually run (with mocked externals)? Verify no import errors.
6. **Integration** — run the full test suite: `PYTHONPATH=src venv/bin/pytest src/tests/ -v`

**Commit:** `git commit -m "test: add adversarial tests for composition root"`
