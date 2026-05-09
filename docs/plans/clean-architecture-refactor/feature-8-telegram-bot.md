# Feature 8 — TelegramBot (Thin UI Handlers)

Refactored Telegram bot with thin UI handlers that delegate to use cases.

---

### Task 8.1: Write failing tests for TelegramBot

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Features 1, 4, 5, 6, 7 (their REVIEW tasks must be complete — the use cases, repo interface, and notifiers must exist)

**Design requirements being tested:**
- `TelegramBot` injected with `ScheduleBookingUseCase`, `RemoveBookingUseCase`, and `IUserRepository` (for authorization checks and listing bookings)
- Deferred injection via `set_use_cases(schedule_uc, remove_uc)` — bot created before use cases are fully wired
- Handlers parse Telegram input, call use cases, and format responses — no business logic inline
- `/start` — authorization check via `user_repo.get_user(user_id)`, welcome message if found
- `/schedule` — lists user's booking goals via `user_repo.get_user(user_id)` then reading `user.booking_goals`
- `/add` — ConversationHandler: day -> time -> class_name -> calls `schedule_uc.execute(user_id, booking_date, class_name)`
- `/remove <idx>` — resolves booking by index from `user.booking_goals`, calls `remove_uc.execute(user_id, job_id)`
- `/cancel` — cancels conversation, clears context

**Files:**
- Create: `src/tests/test_telegram_bot.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_start_handler_authorized_user` | `user_repo.get_user(12345)` returns `User(id=12345, email="a@b.com", password="pw")`. Simulate `/start` | Sends welcome message containing "Welcome" |
| `test_start_handler_unauthorized_user` | `user_repo.get_user(99999)` returns `None`. Simulate `/start` | Sends message containing "don't have power" |
| `test_schedule_handler_lists_bookings` | `user_repo.get_user(12345)` returns `User(id=12345, ..., booking_goals=[BookingGoal(booking_date=datetime(2027, 1, 18, 18, 30), name="WOD", job_id="j1")])`. Simulate `/schedule` | Response contains "WOD" and booking date info |
| `test_schedule_handler_empty_bookings` | User has `booking_goals=[]`. Simulate `/schedule` | Response contains "don't have any class booking" (or similar) |
| `test_add_flow_calls_schedule_use_case` | Simulate full conversation: `/add` -> select day "15-03 (Monday)" -> enter time "18:30" -> select class "WOD". User is authorized | `schedule_uc.execute` called with `user_id=12345`, `booking_date=datetime(2027, 3, 15, 18, 30)`, `class_name="WOD"` |
| `test_add_flow_unauthorized_user` | `user_repo.get_user(99999)` returns `None`. Simulate `/add` | Sends rejection message. `schedule_uc.execute` NOT called |
| `test_add_flow_invalid_time_retries` | Simulate: `/add` -> select day -> enter "25:99" (invalid) | Sends error message about invalid time. Stays in time selection state |
| `test_add_flow_invalid_class_retries` | Simulate: `/add` -> day -> time -> enter "INVALID_CLASS" | Sends error about invalid class name. Stays in class selection state |
| `test_cancel_clears_context` | Start `/add`, then `/cancel` | Sends "Booking cancelled". Conversation ends |
| `test_remove_handler_calls_remove_use_case` | User has `booking_goals=[BookingGoal(..., job_id="job-to-remove")]`. Simulate `/remove 1` | `remove_uc.execute` called with `(user_id, "job-to-remove")` |
| `test_bot_uses_domain_objects_not_dicts` | `/schedule` handler accesses user's booking goals | Handler reads `user.booking_goals` (list of `BookingGoal` objects), NOT `user_schedule_config["bookingGoals"]` (dicts) |

**Data structures referenced:**
- `domain.models.User`, `domain.models.BookingGoal`
- `domain.ports.user_repository.IUserRepository`
- `application.use_cases.schedule_booking.ScheduleBookingUseCase`
- `application.use_cases.remove_booking.RemoveBookingUseCase`

**Setup:**
- Mock dependencies via pytest-mock: `mocker.Mock(spec=IUserRepository)`, `mocker.Mock(spec=ScheduleBookingUseCase)`, `mocker.Mock(spec=RemoveBookingUseCase)`
- Mock `Update`/`Context` objects using `mocker.Mock()` / `mocker.AsyncMock()` for async handlers
- Use pytest fixtures to create the bot with mocked dependencies:
  ```python
  @pytest.fixture
  def telegram_bot(mocker):
      user_repo = mocker.Mock(spec=IUserRepository)
      schedule_uc = mocker.Mock(spec=ScheduleBookingUseCase)
      remove_uc = mocker.Mock(spec=RemoveBookingUseCase)
      bot = TelegramBot(user_repo=user_repo)
      bot.set_use_cases(schedule_uc, remove_uc)
      return bot, user_repo, schedule_uc, remove_uc
  ```
- All mocking uses the `mocker` fixture from pytest-mock (no `unittest.mock` imports)

**Key assertions:**
- Bot delegates to use cases — no booking logic in handlers
- Bot uses `IUserRepository.get_user()` returning `User` objects (not raw repo dicts)
- `/schedule` reads `user.booking_goals` (domain objects), formats them for display
- `/remove` resolves by index from `user.booking_goals`, extracts `job_id`, passes to `remove_uc.execute`
- `set_use_cases` allows deferred injection (bot can be created before use cases exist)

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_telegram_bot.py -v`
Expected: ALL tests FAIL (new TelegramBot class at new path not found)

**Commit:** `git commit -m "test: add failing tests for TelegramBot thin UI handlers"`

---

### Task 8.2: Implement TelegramBot

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 8.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 8.1 pass.

**Files:**
- Create: `src/infrastructure/telegram/bot.py`
- Reference: `src/tests/test_telegram_bot.py`

**What to implement:**

```python
class TelegramBot:
    def __init__(self, user_repo: IUserRepository) -> None
    def set_use_cases(self, schedule_uc: ScheduleBookingUseCase, remove_uc: RemoveBookingUseCase) -> None
    def run(self) -> None
    def send_message(self, chat_id: int, message: str) -> None
```

**Handler implementations:**

- `__start_handler`: check `self._user_repo.get_user(user_id)`. If `None`, send rejection. Else send welcome.
- `__schedule_handler`: `user = self._user_repo.get_user(user_id)`. Format `user.booking_goals` as numbered list. Each goal: `f"{idx+1}. {goal.booking_date.strftime('%d-%m-%Y %H:%M')} {goal.name}"`. If empty: "You don't have any class booking scheduled yet".
- `__start_booking_handler`: authorization check, show day keyboard, return `SELECTING_DAY`.
- `__day_selected_handler`: parse "DD-MM (Weekday)" -> extract "DD-MM" -> combine with current year -> handle year rollover. Same logic as existing.
- `__time_selected_handler`: validate "HH:MM" format. Same logic as existing.
- `__class_name_selected_handler`: validate class name. Build `booking_date` from context. Call `self._schedule_uc.execute(user_id=user_id, booking_date=booking_date, class_name=class_name)`. Send confirmation.
- `__cancel_booking_handler`: clear context, send cancellation message.
- `__remove_booking_handler`: parse index from args. Get user via `self._user_repo.get_user(user_id)`. Index into `user.booking_goals`. Call `self._remove_uc.execute(user_id, selected_goal.job_id)`. Send confirmation.

**Key changes from old `telegram_logger.py`:**
- Constructor takes `IUserRepository` instead of `JsonRepository`
- Use cases injected via `set_use_cases()` instead of `BookingScheduler`
- `__schedule_handler` reads `user.booking_goals` (domain objects) not raw dicts
- `__class_name_selected_handler` calls `schedule_uc.execute()` instead of `scheduler.schedule_unique_execution()`
- `__remove_booking_handler` calls `remove_uc.execute()` instead of `scheduler.remove_unique_execution()`
- No inline booking logic — pure delegation

**DI registration table:** N/A

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_telegram_bot.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement TelegramBot with thin UI handlers"`

---

### Task 8.3: Adversarial review of TelegramBot

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 8.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- Bot injected with `IUserRepository`, `ScheduleBookingUseCase`, `RemoveBookingUseCase`
- Deferred injection via `set_use_cases`
- Handlers are thin — no business logic, only parse input and call use cases
- `/schedule` uses `user.booking_goals` (domain objects, not raw dicts)
- `/remove` resolves by index into `user.booking_goals`, extracts `job_id`
- `/add` conversation calls `schedule_uc.execute` at the end

**Review checklist:**
1. **Requirements compliance** — all handlers delegate to use cases, no inline logic
2. **Test adequacy** — do tests prove no business logic in handlers? What if we removed the use case and inlined booking logic — would tests catch it?
3. **Edge cases:**
   - What if `set_use_cases` is never called and a handler runs? (Should fail gracefully or raise)
   - What if `/remove` index is out of bounds?
   - What if the use case raises an exception (e.g., `BookingFailed`)? Does the bot handle it gracefully?
4. **Error handling** — are exceptions from use cases caught and turned into user-friendly messages?
5. **Integration** — does `send_message` still work for notification callbacks?

**Commit:** `git commit -m "test: add adversarial tests for TelegramBot"`
