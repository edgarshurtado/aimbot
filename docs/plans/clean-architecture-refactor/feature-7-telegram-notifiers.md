# Feature 7 — TelegramGroupNotifier + TelegramUserNotifier

Infrastructure adapters implementing `IGroupNotifier` and `IUserNotifier`.

---

### Task 7.1: Write failing tests for Telegram notifiers

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- `TelegramGroupNotifier` implements `IGroupNotifier`
- `TelegramGroupNotifier.notify_group(message: str)` — sends message to the hardcoded group channel via HTTP POST (same as old `TelegramLogger.send_message`)
- No dependency on the Telegram bot library — uses raw `requests.post`
- Group ID: `-1002328222855` (hardcoded, same as old `TelegramLogger`)
- Bot API URL: `https://api.telegram.org/bot{token}/sendMessage`
- `TelegramUserNotifier` implements `IUserNotifier`
- `TelegramUserNotifier.notify_user(user_id: int, message: str)` — sends message to individual user via `TelegramBot.send_message`
- `TelegramUserNotifier` wraps a reference to the bot's `send_message` method (or the bot itself)

**Files:**
- Create: `src/tests/test_telegram_notifiers.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_group_notifier_implements_interface` | Create `TelegramGroupNotifier()` | `isinstance(notifier, IGroupNotifier)` is `True` |
| `test_group_notifier_sends_http_post` | Mock `requests.post`. Call `notifier.notify_group("Booking confirmed!")` | `requests.post` called once. URL contains `/sendMessage`. Params include `chat_id=-1002328222855` and `text="Booking confirmed!"` |
| `test_group_notifier_uses_correct_token` | Set env var `TELEGRAM_BOT_TOKEN_DEV="test-token-123"`. Create notifier | URL contains `bottest-token-123` |
| `test_user_notifier_implements_interface` | Create `TelegramUserNotifier(bot_send_fn)` with a mock callable | `isinstance(notifier, IUserNotifier)` is `True` |
| `test_user_notifier_sends_message_to_user` | Mock callable `send_fn = Mock()`. Create `TelegramUserNotifier(send_fn)`. Call `notifier.notify_user(user_id=12345, message="Your class is booked!")` | `send_fn` called with `chat_id=12345, message="Your class is booked!"` (or equivalent kwargs) |
| `test_user_notifier_passes_user_id_as_chat_id` | Call `notify_user(user_id=99999, message="test")` | `send_fn` called with `chat_id=99999` — proving `user_id` maps to `chat_id` |

**Data structures referenced:**
- `domain.ports.notifier.IGroupNotifier`, `IUserNotifier`

**Setup:**
- Group notifier: use `mocker.patch("requests.post")` from the `mocker` fixture, set `TELEGRAM_BOT_TOKEN_DEV` env var via `monkeypatch` fixture
- User notifier: pass `mocker.Mock()` callable as the send function
- All mocking uses the `mocker` fixture from pytest-mock (no `unittest.mock` imports)

**Key assertions:**
- Group notifier uses `requests.post` directly — NOT the Telegram bot library
- User notifier delegates to an injected callable — NOT `requests.post`
- Both implement their respective ABC interfaces

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_telegram_notifiers.py -v`
Expected: ALL tests FAIL (module not found)

**Commit:** `git commit -m "test: add failing tests for Telegram notifiers"`

---

### Task 7.2: Implement TelegramGroupNotifier + TelegramUserNotifier

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 7.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 7.1 pass.

**Files:**
- Create: `src/infrastructure/telegram/group_notifier.py`
- Create: `src/infrastructure/telegram/user_notifier.py`
- Reference: `src/tests/test_telegram_notifiers.py`

**What to implement:**

**`infrastructure/telegram/group_notifier.py`:**

```python
class TelegramGroupNotifier(IGroupNotifier):
    def __init__(self) -> None
    def notify_group(self, message: str) -> None
```

- Reads token via `get_telegram_token()` (reuse the existing function from `telegram_logger.py` or copy it)
- `notify_group`: `requests.post(f"https://api.telegram.org/bot{token}/sendMessage", params={"chat_id": -1002328222855, "text": message})`
- Exactly the same logic as old `TelegramLogger.send_message`

**`infrastructure/telegram/user_notifier.py`:**

```python
class TelegramUserNotifier(IUserNotifier):
    def __init__(self, send_fn: Callable[[int, str], None]) -> None
    def notify_user(self, user_id: int, message: str) -> None
```

- `send_fn` is injected — in production this will be `TelegramBot.send_message` (bound method)
- `notify_user`: calls `self._send_fn(chat_id=user_id, message=message)`

**DI registration table:** N/A

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_telegram_notifiers.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement TelegramGroupNotifier and TelegramUserNotifier"`

---

### Task 7.3: Adversarial review of Telegram notifiers

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 7.2 must be complete

**Your role:** Adversarial reviewer.

**Design requirements to verify:**
- `TelegramGroupNotifier` implements `IGroupNotifier`, uses raw `requests.post`, hardcoded group ID
- `TelegramUserNotifier` implements `IUserNotifier`, delegates to injected callable
- No dependency on telegram bot library in group notifier
- Group ID is `-1002328222855`

**Review checklist:**
1. **Requirements compliance** — each requirement verified
2. **Test adequacy** — do tests verify the HTTP method (POST not GET)?
3. **Edge cases** — what if token env var is not set? What if `send_fn` raises?
4. **Error handling** — should notification failures propagate or be swallowed? (Design doesn't specify — note this)
5. **Integration** — does `get_telegram_token()` work the same way?

**Commit:** `git commit -m "test: add adversarial tests for Telegram notifiers"`
