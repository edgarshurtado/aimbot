# Integration Triplet — End-to-End Verification

Verifies that all features work together after isolated unit testing.

---

## Mock Boundary Table

| Feature | Mock Used | Real Connection Hidden | Integration Test |
|---------|-----------|----------------------|-----------------|
| F1 (JsonRepository) | File I/O tested against `test_schedule.json` | Production `schedule.json` path resolution from new `infrastructure/persistence/` location | Verify repository reads/writes from correct path when instantiated without explicit filename |
| F2 (AimHarderClient) | `mocker.patch("requests.Session")` | Real HTTP to aimharder.com | N/A — external API, keep mocked. Verify client can be constructed by factory with real config values |
| F3 (APSchedulerAdapter) | `mocker.Mock()` for on_job_execute | Handler wiring to `ExecuteBookingUseCase.execute` | Schedule a job, let it fire, verify `ExecuteBookingUseCase.execute` is called |
| F4 (ScheduleBookingUseCase) | `mocker.Mock(spec=IJobScheduler)`, `mocker.Mock(spec=IBookingRepository)`, `mocker.Mock(spec=IGymPlatformConfig)` | Real adapter interactions | Call `schedule_uc.execute()` with real `APSchedulerAdapter` + real `JsonRepository` + real `AimHarderClientFactory` |
| F5 (ExecuteBookingUseCase) | `mocker.Mock(spec=IGymClientFactory)`, `mocker.Mock(spec=IUserNotifier)`, `mocker.Mock(spec=IGroupNotifier)` | Real gym client creation, real notification delivery | Call `execute_uc.execute()` with real `JsonRepository` and mocked gym client (external API) |
| F6 (RemoveBookingUseCase) | `mocker.Mock(spec=IJobScheduler)`, `mocker.Mock(spec=IBookingRepository)` | Real adapter interactions | Call `remove_uc.execute()` with real `APSchedulerAdapter` + real `JsonRepository` |
| F7 (Telegram Notifiers) | `mocker.patch("requests.post")`, `mocker.Mock()` for send_fn | Real HTTP for group notifier, real bot for user notifier | N/A — external Telegram API, keep mocked. Verify notifiers can be constructed with real dependencies |
| F8 (TelegramBot) | `mocker.Mock(spec=IUserRepository)`, `mocker.Mock(spec=ScheduleBookingUseCase)`, `mocker.Mock(spec=RemoveBookingUseCase)` | Real use case execution from handlers | N/A — Telegram bot requires polling infrastructure. Verify `set_use_cases` wiring works with real use case instances |
| F9 (Composition Root) | All infrastructure mocked | Full wiring | Startup recovery: create all real objects (except external APIs), run recovery loop, verify goals are scheduled in APScheduler |

---

### Task I.1: Write integration tests

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** All features (F1-F9) must be complete

**Design requirements being tested:**
- All components wire together correctly in the composition root
- Startup recovery re-schedules persisted booking goals
- APScheduler fires jobs that invoke `ExecuteBookingUseCase.execute`
- Use cases interact with real repositories (read/write to test JSON file)
- The complete booking flow: schedule -> job fires -> execute -> clean up goal

**Files:**
- Create: `src/tests/test_integration.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_full_wiring_no_import_errors` | Import all production modules: `infrastructure.persistence.json_repository`, `infrastructure.aimharder.client_factory`, `infrastructure.scheduling.apscheduler`, `infrastructure.telegram.bot`, `infrastructure.telegram.group_notifier`, `infrastructure.telegram.user_notifier`, `application.use_cases.schedule_booking`, `application.use_cases.execute_booking`, `application.use_cases.remove_booking`, `domain.models`, `domain.exceptions` | All imports succeed — no `ModuleNotFoundError`, no circular imports |
| `test_schedule_then_remove_roundtrip` | Create real `JsonRepository(test_schedule.json)`, real `APSchedulerAdapter`, real `AimHarderClientFactory`, real `ScheduleBookingUseCase`, real `RemoveBookingUseCase`. Call `schedule_uc.execute(user_id=66666666, booking_date=datetime(2027, 6, 15, 10, 0), class_name="WOD")`. Then find the goal via repo and call `remove_uc.execute(user_id, goal.job_id)` | After schedule: user has 1 booking goal in repo. After remove: user has 0 booking goals. APScheduler job is gone |
| `test_startup_recovery_with_real_components` | Seed `test_schedule.json` with a user having 1 booking goal. Create all real objects. Run the startup recovery loop (same as `main.py`) | `APSchedulerAdapter` has a scheduled job. Repo's booking goal has an updated `job_id` (dedup fired) |
| `test_execute_booking_with_real_repo_mocked_http` | Create real `JsonRepository`, real `ExecuteBookingUseCase` with mocked `IGymClientFactory` (external API). Mock client returns `[GymClass(id="42", name="WOD", time="10:00", spots_available=5, max_spots=20)]`. Seed repo with user + booking goal. Call `execute_uc.execute(66666666, datetime(2027, 6, 15, 10, 0), "WOD")` | Client's `book_class` called. Booking goal removed from repo. Notifiers called |
| `test_apscheduler_fires_execute_handler` | Create real `APSchedulerAdapter(on_job_execute=mock_handler)`. Schedule a job with `run_at` in the immediate past. Start scheduler. Wait briefly | `mock_handler` is called with the correct `(user_id, booking_date, class_name)` args |
| `test_json_repository_path_from_infrastructure_location` | Create `JsonRepository('test_schedule.json')` from the new `infrastructure.persistence` module | Repository finds and reads the file correctly (path resolution works despite module being in a subdirectory) |

**Prerequisites check:**
- No additional packages needed — all integration tests use real Python objects with only external APIs mocked
- `test_schedule.json` already exists and has the required test user

**Setup:**
- Real objects for internal components, mocks only for external APIs (aimharder.com HTTP, Telegram API)
- Use `test_schedule.json` as the backing file
- Clean up after each test (restore `test_schedule.json` to original state)

**Key assertions:**
- No circular imports
- Real `JsonRepository` and real use cases interact correctly (domain objects flow end-to-end)
- APScheduler actually fires handlers with correct arguments
- Dedup works in real startup recovery scenario

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_integration.py -v`
Expected: ALL tests FAIL (integration points not yet verified)

**Commit:** `git commit -m "test: add integration tests for clean architecture wiring"`

---

### Task I.2: Fix integration failures

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task I.1 must be complete

**Goal:** Fix any failures discovered by the integration tests.

**Common expected issues:**
- `JsonRepository` file path resolution from `infrastructure/persistence/` subdirectory (the `db_file_name` may need to resolve relative to `src/`, not the module's directory)
- Missing `__init__.py` files in package directories
- Import path mismatches between test imports and actual module locations
- APScheduler timing issues in tests (past `run_at` behavior)

**Files:**
- Modify: whichever files the integration tests reveal as broken
- Reference: `src/tests/test_integration.py`

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_integration.py -v`
Expected: ALL tests PASS

Then run the FULL test suite:
Run: `PYTHONPATH=src venv/bin/pytest src/tests/ -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "fix: resolve integration issues in clean architecture wiring"`

---

### Task I.3: Final adversarial review

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task I.2 must be complete

**Your role:** Final adversarial reviewer for the ENTIRE refactor.

**Design requirements to verify (full checklist from design doc):**

**Domain Layer:**
- [ ] `GymClass`, `BookingGoal`, `User` dataclasses in `domain/models.py`
- [ ] `BookingGoal.booking_date` is `datetime`, not string
- [ ] All exceptions in `domain/exceptions.py`
- [ ] `IUserRepository` port with `get_user`, `get_all_users`
- [ ] `IBookingRepository` port with `get_user_bookings`, `add_booking_goal`, `remove_booking_goal`, `find_booking_goal`
- [ ] `IGymPlatformConfig`, `IGymClient`, `IGymClientFactory` ports
- [ ] `IJobScheduler` port with `start`, `schedule_job`, `remove_job`
- [ ] `IUserNotifier`, `IGroupNotifier` ports

**Application Layer:**
- [ ] `ScheduleBookingUseCase` — does NOT depend on `ExecuteBookingUseCase`
- [ ] `ExecuteBookingUseCase` — `booking_date` IS the target day (no `days_in_advance`)
- [ ] `RemoveBookingUseCase` — scheduler first, then repo

**Infrastructure Layer:**
- [ ] `AimHarderClient` implements `IGymClient`, returns `GymClass` objects
- [ ] `AimHarderClientFactory` implements both `IGymClientFactory` and `IGymPlatformConfig`
- [ ] `JsonRepository` implements both `IUserRepository` and `IBookingRepository`, returns domain objects
- [ ] `APSchedulerAdapter` implements `IJobScheduler`, `DateTrigger` only
- [ ] `TelegramBot` — thin handlers, delegates to use cases
- [ ] `TelegramGroupNotifier` implements `IGroupNotifier`
- [ ] `TelegramUserNotifier` implements `IUserNotifier`

**Composition Root:**
- [ ] Pure wiring, no business logic
- [ ] Startup recovery re-schedules all persisted goals
- [ ] Recurrent booking code deleted

**Deleted files:**
- [ ] `src/booking_scheduler.py` deleted
- [ ] `src/telegram_logger.py` deleted
- [ ] `src/domain/ScheduleManager.py` deleted
- [ ] `src/tests/test_main.py` deleted

**Review actions:**
1. Run full test suite: `PYTHONPATH=src venv/bin/pytest src/tests/ -v`
2. Verify no import errors: `PYTHONPATH=src python -c "from infrastructure.persistence.json_repository import JsonRepository; from infrastructure.aimharder.client_factory import AimHarderClientFactory; from infrastructure.scheduling.apscheduler import APSchedulerAdapter; from infrastructure.telegram.bot import TelegramBot; from application.use_cases.schedule_booking import ScheduleBookingUseCase; from application.use_cases.execute_booking import ExecuteBookingUseCase; from application.use_cases.remove_booking import RemoveBookingUseCase; print('OK')"`
3. Verify old files are gone: `ls src/booking_scheduler.py src/telegram_logger.py src/domain/ScheduleManager.py src/tests/test_main.py` should all fail
4. Check for any remaining imports of old modules
5. Run `make format/check` to verify code style

**If additional tests written:** commit them.
**Verdict:** PASS or FAIL with detailed findings.

**Commit:** `git commit -m "test: final adversarial review of clean architecture refactor"`
