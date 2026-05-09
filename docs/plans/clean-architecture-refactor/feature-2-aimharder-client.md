# Feature 2 — AimHarderClient + AimHarderClientFactory

Moves `AimHarderClient` to infrastructure layer, creates `AimHarderClientFactory` implementing `IGymClientFactory` + `IGymPlatformConfig`.

---

### Task 2.1: Write failing tests for AimHarderClient + Factory

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 0

**Design requirements being tested:**
- `AimHarderClient` implements `IGymClient` — same HTTP logic as existing `src/client.py` but `get_classes()` returns `list[GymClass]` domain objects (not raw dicts)
- `AimHarderClient.book_class(target_day, class_id) -> None` — no `family_id` param (simplified)
- `AimHarderClientFactory` implements `IGymClientFactory` and `IGymPlatformConfig`
- `AimHarderClientFactory.__init__(box_id: int, box_name: str)`
- `AimHarderClientFactory.create(email, password) -> AimHarderClient`
- `AimHarderClientFactory.booking_trigger_time(class_date) -> datetime` returns `class_date - timedelta(days=3)`
- `GymClass` domain object has: `id: str`, `name: str`, `time: str` (HH:MM), `spots_available: int`, `max_spots: int`
- Client normalizes `timeid` format (e.g., `"1100_60"`) to `HH:MM` format (e.g., `"11:00"`) when constructing `GymClass`

**Files:**
- Create: `src/tests/test_aimharder.py`

**Test cases:**

| Test | Scenario | Expected |
|------|----------|----------|
| `test_client_login_success` | Mock `requests.Session.post` to return HTML with empty error span `<span id="loginErrors"></span>` | `AimHarderClient("foo@bar.com", "pass", 9824, "themonkeybox")` creates without raising |
| `test_client_login_too_many_attempts` | Mock login to return HTML with `<span id="loginErrors">demasiadas veces</span>` | Raises `TooManyWrongAttempts` |
| `test_client_login_incorrect_credentials` | Mock login to return HTML with `<span id="loginErrors">incorrecto</span>` | Raises `IncorrectCredentials` |
| `test_get_classes_returns_gym_class_objects` | Mock login success. Mock GET to return `{"bookings": [{"id": "42", "timeid": "1100_60", "className": "WOD", "plazasDisp": 5, "plazas": 20}]}` | Returns `list[GymClass]`. First element: `GymClass(id="42", name="WOD", time="11:00", spots_available=5, max_spots=20)` |
| `test_get_classes_empty_bookings` | Mock GET to return `{"bookings": []}` | Returns `[]` (empty list, not `None`) |
| `test_get_classes_no_bookings_key` | Mock GET to return `{}` | Returns `[]` (empty list, not `None`) |
| `test_get_classes_normalizes_timeid_to_hhmm` | Mock GET with `{"bookings": [{"id": "1", "timeid": "0830_60", "className": "OPEN", "plazasDisp": 3, "plazas": 15}]}` | `GymClass.time == "08:30"` |
| `test_book_class_success` | Mock login success. Mock POST to return `{}` with status 200 | `client.book_class(datetime(2027, 3, 2), "42")` returns `None` without raising |
| `test_book_class_no_credit` | Mock POST to return `{"bookState": -2}` with status 200 | Raises `BookingFailed` with message containing "No credit" |
| `test_book_class_error_response` | Mock POST to return `{"errorMssg": "some error"}` with status 200 | Raises `BookingFailed` |
| `test_book_class_server_error` | Mock POST with status 500 | Raises `BookingFailed` |
| `test_factory_create_returns_client` | Create `AimHarderClientFactory(box_id=9824, box_name="themonkeybox")`. Mock login success. Call `factory.create("foo@bar.com", "pass")` | Returns `AimHarderClient` instance (or an `IGymClient` — type check against interface) |
| `test_factory_booking_trigger_time` | `factory.booking_trigger_time(datetime(2027, 3, 15, 18, 30))` | Returns `datetime(2027, 3, 12, 18, 30)` (exactly 3 days earlier) |
| `test_factory_implements_both_interfaces` | `isinstance(factory, IGymClientFactory)` and `isinstance(factory, IGymPlatformConfig)` | Both return `True` |

**Data structures referenced:**
- `domain.models.GymClass(id: str, name: str, time: str, spots_available: int, max_spots: int)`
- `domain.ports.gym_client.IGymClient`, `IGymClientFactory`, `IGymPlatformConfig`
- `domain.exceptions.TooManyWrongAttempts`, `IncorrectCredentials`, `BookingFailed`

**Setup:**
- Use `mocker.patch("requests.Session.post")` for login via the `mocker` fixture from pytest-mock
- Use `mocker.patch("requests.Session.get")` for `get_classes`
- Use `mocker.patch("requests.Session.post")` for `book_class`
- Factory tests: a `factory` fixture that creates `AimHarderClientFactory(box_id=9824, box_name="themonkeybox")`
- All mocking uses the `mocker` fixture (no `unittest.mock` imports)

**Key assertions:**
- `get_classes` returns `list[GymClass]` (domain objects), NOT raw dicts
- `get_classes` never returns `None` — returns empty list instead
- `timeid` -> `time` normalization: `"1100_60"` becomes `"11:00"`, `"0830_60"` becomes `"08:30"`
- Factory's `booking_trigger_time` subtracts exactly 3 days

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_aimharder.py -v`
Expected: ALL tests FAIL (module/class not found)

**Commit:** `git commit -m "test: add failing tests for AimHarderClient and AimHarderClientFactory"`

---

### Task 2.2: Implement AimHarderClient + AimHarderClientFactory

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 2.1 must be complete

**Goal:** Write the minimal code to make ALL tests from Task 2.1 pass.

**Files:**
- Create: `src/infrastructure/aimharder/client.py`
- Create: `src/infrastructure/aimharder/client_factory.py`
- Reference: `src/tests/test_aimharder.py`

**What to implement:**

**`infrastructure/aimharder/client.py` — `AimHarderClient(IGymClient)`:**

```python
class AimHarderClient(IGymClient):
    def __init__(self, email: str, password: str, box_id: int, box_name: str) -> None
    @staticmethod
    def _login(email: str, password: str) -> Session
    def get_classes(self, target_day: datetime) -> list[GymClass]
    def book_class(self, target_day: datetime, class_id: str) -> None
```

- `_login`: same HTML parsing as existing `src/client.py`
- `get_classes`: same HTTP GET, but maps response dicts to `GymClass` objects. **Normalization:** extract hours and minutes from `timeid` (format `"HHMM_duration"`, e.g., `"1100_60"`) -> `time = "11:00"`. Map `className` -> `name`, `plazasDisp` -> `spots_available`, `plazas` -> `max_spots`.
- `get_classes` must return `[]` when response has no `"bookings"` key or bookings is `None`
- `book_class`: same POST logic as existing `src/client.py` but without `family_id` parameter

**`infrastructure/aimharder/client_factory.py` — `AimHarderClientFactory(IGymClientFactory, IGymPlatformConfig)`:**

```python
class AimHarderClientFactory(IGymClientFactory, IGymPlatformConfig):
    def __init__(self, box_id: int, box_name: str) -> None
    def create(self, email: str, password: str) -> AimHarderClient
    def booking_trigger_time(self, class_date: datetime) -> datetime
```

- `create`: returns `AimHarderClient(email, password, self._box_id, self._box_name)`
- `booking_trigger_time`: returns `class_date - timedelta(days=3)`

**Error handling:**

| Condition | Error Type | Response |
|-----------|-----------|----------|
| Login HTML contains "demasiadas veces" | `TooManyWrongAttempts` | Raised from `_login` |
| Login HTML contains "incorrecto" | `IncorrectCredentials` | Raised from `_login` |
| Booking returns `bookState == -2` | `BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)` | Raised from `book_class` |
| Booking returns error fields or non-200 | `BookingFailed(MESSAGE_BOOKING_FAILED_UNKNOWN)` | Raised from `book_class` |

**DI registration table:** N/A — instantiated directly in composition root.

**Verification:**
Run: `PYTHONPATH=src venv/bin/pytest src/tests/test_aimharder.py -v`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement AimHarderClient and AimHarderClientFactory adapters"`

---

### Task 2.3: Adversarial review of AimHarderClient + Factory

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task 2.2 must be complete

**Your role:** Adversarial reviewer. Verify requirements AND try to break it.

**Design requirements to verify:**
- `AimHarderClient` inherits from `IGymClient`
- `get_classes` returns `list[GymClass]` domain objects, never raw dicts or `None`
- `timeid` normalization: `"HHMM_duration"` -> `"HH:MM"` string
- `AimHarderClientFactory` inherits from BOTH `IGymClientFactory` AND `IGymPlatformConfig`
- `booking_trigger_time` returns `class_date - timedelta(days=3)`
- `book_class` simplified: no `family_id` parameter

**Review checklist:**
1. **Requirements compliance** — each requirement maps to actual code
2. **Completeness** — all methods, all interfaces implemented
3. **Test adequacy** — could tests pass with a wrong `timeid` normalization? Test various formats.
4. **Edge cases** — what if `timeid` is `"900_60"` (3-digit)? What if `plazasDisp` or `plazas` is missing from API response? What if `bookings` is `None` vs missing key?
5. **Error handling** — is the login error detection robust?
6. **Integration** — does it use the same HTTP endpoints as the old client?

**Commit:** `git commit -m "test: add adversarial tests for AimHarderClient and Factory"`
