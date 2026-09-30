# Notify the member when a Booking Attempt fails

Today a failed **Booking Attempt** raises out of `ExecuteBookingUseCase` into APScheduler's
worker thread, which logs it and moves on (`apscheduler/executors/base.py:145`). The member is
never told. Their `/schedule` still lists the goal, so they believe a booking is coming.

This change makes every **Booking Attempt** report its outcome to the member and consume its
**Booking Goal**, win or lose.

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | A **Booking Attempt** is terminal. One goal, one attempt, no retries. | The **Booking Window** is a race; a retry policy has no natural stopping rule. Retrying is a separate feature. |
| 2 | The goal is discarded on **every** outcome, regardless of why it failed. | One code path, no recoverable/unrecoverable taxonomy to maintain and keep correct. Accepted cost: an AimBot-side fault (e.g. a platform login change) deletes goals it could in principle have kept. |
| 3 | A **Lapsed Booking Goal** — class already started — is swept silently: no attempt, no message. | `CONTEXT.md` defines it as residue, not intent. Nothing failed *now*, so there is nothing to report. Without this, the first restart after deploy messages members about classes that ended months ago. |
| 4 | Handled inside `ExecuteBookingUseCase`, which then **re-raises**. | The use case already owns notification via `IUserNotifier` (a domain port — no Telegram coupling). Re-raising preserves APScheduler's traceback logging, which matters because the member's message is deliberately curated. |
| 5 | Discard first, then notify — on success and failure alike. | One rule, no asymmetry to explain. Avoids the false-alarm path where a lost confirmation leaves the goal alive, gets re-attempted, is rejected as a duplicate, and tells the member they failed to book a class they are booked into. |
| 6 | Delivery reliability belongs to `TelegramUserNotifier`, not to statement order. | Follows from 5: the narrow window it leaves open (Telegram down at Trigger Time) is closed where the responsibility actually lives. |
| 7 | Reason text comes from `str(exc)` for `BookingFailed`; one fixed line for `AuthenticationFailed`; a generic line for anything else. | `BookingFailed`'s four causes already carry their own member-readable sentence, so no mapping or subclassing is needed and new causes explain themselves. All three auth causes mean the same thing to a member. |
| 8 | Message uses the bot's rich style. The existing success message is left as-is. | The member last saw this class in an `/add` confirmation formatted the same way. Keeps the diff on the failure path. |

Decisions 1 and 2 are recorded as
[ADR-0001](../adr/0001-booking-attempts-consume-their-goal.md), including the alternative that was
rejected and the failure mode that choice accepts.

## Changes

### `src/domain/exceptions.py`

Two constants become member-facing copy and need to say something true:

- `MESSAGE_BOX_IS_CLOSED` → rename to `MESSAGE_TIMETABLE_EMPTY`, text
  `"The gym hasn't published a timetable for that day"`. The current name and text assert a cause
  AimBot never checked — all it knows is that `get_classes` returned an empty list. The new wording
  also matches what the `/add` flow already says for the same condition (`bot.py:199`).
- `MESSAGE_BOOKING_FAILED_UNKNOWN` → `"The gym rejected the booking without saying why"`.
  `"Unknown error"` tells the member nothing.

Callers to update: `execute_booking.py`, `tests/use_cases/test_execute_booking.py`.

### `src/application/use_cases/execute_booking.py`

Add member-facing constants:

```python
MEMBER_MESSAGE_SIGN_IN = "AimBot couldn't sign in to your gym account."
MEMBER_MESSAGE_UNKNOWN = "Something went wrong on our side."
```

Structure of `execute`:

1. **Lapsed guard, first.** `booking_goal.class_start < datetime.now()` → remove the goal, return.
   No login, no timetable fetch, no message. Uses `datetime.now()` directly, matching `bot.py`;
   the codebase has no clock port and this change does not introduce one.
2. **Wrap the rest.** On any exception: remove the goal, notify the member, `raise`.
   The catch is `Exception`, deliberately broad — the point is that no failure stays silent, and
   `get_classes` has no guard around `.json()`, so a 502's HTML body surfaces as a bare
   `ValueError`. `UserNotFound` falls into this bucket too; `JsonRepository.remove_booking_goal`
   (line 113) is a no-op for an unknown user, so the discard is safe.
3. **Success path** keeps its current order and wording, now with the goal removed before the
   notification for consistency with 2.

Reason resolution:

```python
def _member_reason(exc: Exception) -> str:
    if isinstance(exc, BookingFailed):
        return str(exc)
    if isinstance(exc, AuthenticationFailed):
        return MEMBER_MESSAGE_SIGN_IN
    return MEMBER_MESSAGE_UNKNOWN
```

Message:

```
❌ Couldn't book {class_name}
📅 {dd/mm/YYYY HH:MM}
{reason}
```

Because the header now carries the class identity, trim the `MESSAGE_GYM_CLASS_NOT_FOUND` raise
(line 47) back to the bare constant — the name, time and date it currently interpolates would be
printed twice.

### `src/infrastructure/telegram/user_notifier.py`

Bounded retry around `send_fn`. python-telegram-bot has no built-in retry; its own docs state
retrying is the caller's policy.

- Retry on `telegram.error.TimedOut` and `telegram.error.NetworkError`.
- **Do not** retry `telegram.error.BadRequest` or `Forbidden` — `BadRequest` *subclasses*
  `NetworkError`, so a naive `except NetworkError` would hammer a permanently invalid request.
  Exclude them explicitly.
- Honour `telegram.error.RetryAfter.retry_after` when present.
- 3 attempts, short backoff. This runs on an APScheduler worker thread, so a few seconds of
  blocking is acceptable; the scheduler is not the Telegram event loop.
- Raise after exhaustion. Under decision 4 the exception propagates to APScheduler, which logs it
  with the original booking failure chained as `__context__` — so the operator sees both.

This makes `IUserNotifier`'s port contract meaningful: delivery is attempted seriously, and a
failure to deliver is loud.

## Tests

Integration-first, in `test_integration.py`, modelled on `test_execute_booking_with_real_repo_mocked_http`
(line 145): real `JsonRepository`, real use case, aimharder HTTP and Telegram mocked at the edge.
Each asserts **both** halves — the message sent *and* the goal's absence from the JSON file on disk.

1. Booking rejected (200 + `errorMssg`) → member messaged with the rejection wording; goal gone from the file.
2. Login rejected (401 at `LOGIN_ENDPOINT`) → member messaged with the sign-in line; goal gone.
3. Unrecognized fault (HTML body → `ValueError` from `.json()`) → member gets the generic line, not a stack trace; goal gone.
4. Lapsed goal (`class_start` in the past, via freezegun) → no message, no HTTP request at all, goal gone.
5. Notification exhausts its retries → the goal is still gone (decision 5), and the raised error reaches the caller.

Use-case tests in `tests/use_cases/test_execute_booking.py`: update the two existing
`pytest.raises` tests (`test_execute_booking_no_matching_class_raises`, `test_execute_booking_box_closed`)
— the exception still propagates, but they now also assert notification and discard.

Adapter test in `test_telegram_notifiers.py`: retry on `TimedOut`, **no** retry on `BadRequest`,
`RetryAfter.retry_after` honoured.

### Fix required first

`InMemoryBookingRepository.remove_booking_goal` (`tests/fakes.py:41`) calls `list.remove()`, which
raises `ValueError` when the goal is absent. `JsonRepository` (line 113) is tolerant of both an
unknown user and an absent goal. This change makes discard run on paths where the goal may not be
there (`UserNotFound`, a double-fire), so the fake must match the real repository's tolerance or it
will fail tests for behaviour that works in production.

## Out of scope

- **Wiring `IGroupNotifier`.** Re-raising already routes tracebacks to the container logs. Noted as
  a follow-up: alerting the group on the unrecognized-failure bucket is the early warning for the
  class of fault recorded in the silent-booking-failure notes.
- **Realigning the success message** to the bot's rich style.
- **The cross-loop `send_message` hazard.** `bot.py:66-74` builds a fresh event loop per call from
  APScheduler's worker thread while `run_polling()` owns another on the main thread. The retry makes
  this less likely to lose a message but does not fix it. Separate change.
- **Retrying the booking itself** (decision 1).

## Interaction with existing follow-ups

Decisions 2 and 3 subsume the planned *"clean up Lapsed Booking Goals"* follow-up. Goals no longer
accumulate — every attempt consumes its goal, and anything already lapsed is swept on its next
firing. `/schedule` stops showing residue at positions 1, 2, 3 without a separate cleanup pass.

The other two follow-ups (rejecting two goals at the same start time, reimplementing `/remove`) are
untouched.
